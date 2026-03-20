# |-----------Module pour le debug---------|
from icecream import ic
# |-----------Module d'envrionnement---------|
from os import getenv
from os.path import join as pjoin, dirname, abspath
import sys
sys.path.append(abspath(dirname(__file__) + "/.."))
from dotenv import load_dotenv
# # |-----------Module pour le projet---------|
from notion_client import Client, AsyncClient
from utility import JsonFile
from settings import DB_PATH, workspace, logger
from backend import *
import turso
from turso.sync import ConnectionSync
import aiosqlite
import asyncio
from datetime import datetime as dt, timedelta
from typing import Generator, AsyncGenerator



load_dotenv(dotenv_path=pjoin(workspace, 'settings', '.env'))


client_notion = AsyncClient(auth=getenv("NOTION_TOKEN_CARNET"))





class SerieNotionPolling(Serie):
    def __init__(self, id: str, data: dict) -> None:
        self.id: str = id
        self.exo: Exercice = self._parse_exo(data)
        self.date: dt = self._parse_date(data)
        self.num: int = int(JsonFile.safe_get(data, "Sets.title.0.plain_text"))
        self.reps: int = int(JsonFile.safe_get(data, "Reps.number"))
        self.poids: float = float(JsonFile.safe_get(data, "Poids.number"))
        self.rpe: int = int(JsonFile.safe_get(data, "RPE.select.name"))
        self.seance: Seance = self._parse_seance(data)


    def _parse_exo(self, data: dict) -> Exercice:
        exo_id = JsonFile.safe_get(data, "Exercise.relation.0.id")
        return Exercice(id=exo_id)
            
        
    def _parse_date(self, data: dict) -> dt:
        date_str = JsonFile.safe_get(data, "Date.date.start")
        return dt.fromisoformat(date_str)

    def _parse_seance(self, data: dict) -> Seance:
        seance_id = JsonFile.safe_get(data, "Weekly Split Schedule.relation.0.id")
        return Seance(id=seance_id)
            

    
    

class SeanceNotionPolling(Seance):
    def __init__(self, id: str, data: dict) -> None:
        self.id: str = id
        self.name: str = JsonFile.safe_get(data, "Name.title.0.plain_text")
        self.body_part: str = JsonFile.safe_get(data, "Body Part.select.name")
        self.date: dt = self._parse_date(data)
        self.duration: timedelta = self._parse_duration(data)
        self.rpe: int = JsonFile.safe_get(data, "RPE.formula.number")
        
    
    def _parse_date(self, data: dict):
        date_str = JsonFile.safe_get(data, "Date.date.start")
        if not date_str:
            raise ValueError(f"Missing or empty date in Notion data for {self.__class__.__name__} id={getattr(self, 'id', 'unknown')}")

        return dt.fromisoformat(date_str)
        
    def _parse_duration(self, data):
        try:
            start = self.date
            end_str = JsonFile.safe_get(data, "Date.date.end")
            end = dt.fromisoformat(end_str)
            return end - start
        except TypeError:
            logger.warning(f"{self.__repr__} has no end date, setting duration to 0.")
            return timedelta(0)

    





class NotionAPI():
    def __init__(self, client: AsyncClient, turso_db: TursoDB=None) -> None:
        # ExoDB(db_path=DB_PATH,  turso_client=turso_db.conn).sync_from_notion(client_notion=client)
        self.turso_db = turso_db
        self.WEEKLY_SPLIT_SCHEDULES_DS_ID = "848c44b2-c392-4618-9c5a-a761cd9b81e0"
        self.HISTORY_DS_ID = "5e1bdaf9-cc8d-48b5-ab26-205dcbf47d33"

    async def open_database(self, data_source_id: str, filter: dict = None) -> AsyncGenerator[dict]:
        """Yields all the children of the page 'ZtH Carnet de bord'"""
        params = {
            "sorts": [
                {
                    "property": "Date",
                    "direction": "descending"
                }
            ],
            "filter": filter
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        response = await client_notion.data_sources.query(
            data_source_id,
            **params
        )
        for r in response['results']:
            yield r

        while response.get('has_more'):
            response = await client_notion.data_sources.query(
                data_source_id, 
                start_cursor=response['next_cursor'],
                **params
            )
            for r in response['results']:
                yield r

    
    async def get_all_seance(self) -> AsyncGenerator[Seance]:
        async for page in self.open_database(self.WEEKLY_SPLIT_SCHEDULES_DS_ID):
            try:
                yield SeanceDB(page['id'])
            except NotInDBError:
                seance = SeanceNotionPolling(page['id'], page['properties'])
                seance.save_to_db(connection=self.turso_db.conn)
                yield seance
                
    async def get_all_series(self) -> AsyncGenerator[Serie]:
        async for page in self.open_database(self.HISTORY_DS_ID):
            try:
                yield SerieDB(page['id'])
            except NotInDBError:
                serie = SerieNotionPolling(page['id'], page['properties'])
                serie.save_to_db(connection=self.turso_db.conn)
                yield serie

    async def get_last_recent_seance(self) -> Seance:
        conn = await aiosqlite.connect(DB_PATH)
        async with conn.execute("SELECT * FROM seances ORDER BY date_ts DESC LIMIT 1") as cur:
            row = await cur.fetchone()
        
        await conn.close()
        if row:
            return Seance(id=row[0], name=row[1], date=dt.fromtimestamp(row[2]), body_part=row[3], duration=timedelta(seconds=row[4]))
        else:
            logger.warning("No recent seance found in database.")
            return None

    async def fetch_recent_seances(self) -> AsyncGenerator[Seance]:
        seance = await self.get_last_recent_seance()
        logger.info(f"Starting after {seance}")
        
        if seance:
            filter = {
                "property": "Date",
                "date": {
                    "after": seance.date.isoformat()
                }
            }
            
            pages_generator = self.open_database(self.WEEKLY_SPLIT_SCHEDULES_DS_ID, filter=filter)
        else:
            pages_generator = self.open_database(self.WEEKLY_SPLIT_SCHEDULES_DS_ID)

        async for page in pages_generator:
            seance = SeanceNotionPolling(page['id'], page['properties'])
            seance.save_to_db(connection=self.turso_db.conn)
            yield seance
    
    async def get_last_recent_serie(self) -> Serie:
        conn = await aiosqlite.connect(DB_PATH)
        async with conn.execute("SELECT * FROM series ORDER BY date_ts DESC LIMIT 1") as cur:
            row = await cur.fetchone()
        
        await conn.close()
        if row:
            return Serie(id=row[0], seance=Seance(id=row[1]), num=row[2], exo=Exercice(id=row[3]), reps=row[4], poids=row[5], date=dt.fromtimestamp(row[6]))
        else:
            logger.warning("No recent serie found in database.")
            return None

    async def fetch_recent_series(self) -> AsyncGenerator[Serie]:
        serie = await self.get_last_recent_serie()
        logger.info(f"Starting after {serie}")
        
        if serie:
            filter = {
                "property": "Date",
                "date": {
                    "after": serie.date.isoformat()
                }
            }
            
            pages_generator = self.open_database(self.HISTORY_DS_ID, filter=filter)
        else:
            pages_generator = self.open_database(self.HISTORY_DS_ID)

        async for page in pages_generator:
            serie = SerieNotionPolling(page['id'], page['properties'])
            serie.save_to_db(connection=self.turso_db.conn)
            yield serie

    async def fetch_recent_data(self) -> AsyncGenerator[tuple[Seance, list[Serie]]]:
        async for seance in self.fetch_recent_seances():
            seance.save_to_db(connection=self.turso_db.conn)
            series = []
            async for serie in self.fetch_recent_series():
                serie.save_to_db(connection=self.turso_db.conn)
                if serie.seance.id == seance.id:
                    series.append(serie)
            yield seance, series



async def main():
    logger.debug("Starting main function")
    # turso_db = TursoDB(
    #     path=DB_PATH, 
    #     remote_url=getenv("TURSO_DATABASE_URL"), 
    #     auth_token=getenv("TURSO_AUTH_TOKEN")
    # )
    # init_db(turso_db.conn)
    # turso_db.sync()

    # app = NotionAPI(client=client_notion, turso_db=turso_db)
    app = NotionAPI(client=client_notion)
    async for page in app.open_database(app.HISTORY_DS_ID):
        ic(page)
        serie = SerieNotionPolling(page['id'], page['properties'])
        ic(serie.__dict__)
        break
    # recent_seances = [data async for data in app.fetch_recent_seances()]
    # recent_series = [data async for data in app.fetch_recent_series()]
    # recent_data = [data async for data in app.fetch_recent_data()]
    # recent_seances, recent_series = zip(*recent_data) if recent_data else ([], [])

    # ic(len(list(recent_seances)))
    # ic(len(list(recent_series)))
    
    # turso_db.conn.push()  # Ensure all local changes are pushed to the remote database
    # turso_db.conn.close()


if __name__=='__main__':
    logger.debug("Starting script")
    try:
        asyncio.run(main())
        
    except (ConnectError, RemoteProtocolError) as e:
        logger.error(f"Problème de connexion à l'API Notion: {e}", exc_info=True)
        
    except turso.lib.DatabaseError as e:
        logger.error(f"Problème de connexion à la base de données: {e}", exc_info=True)

    logger.debug("Fin du script")
    