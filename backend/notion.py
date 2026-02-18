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
import sqlite3
from turso.sync import ConnectionSync
import aiosqlite
import asyncio
from datetime import datetime as dt, timedelta
from typing import Generator, AsyncGenerator



load_dotenv(dotenv_path=pjoin(workspace, 'settings', '.env'))


client_notion = AsyncClient(auth=getenv("NOTION_TOKEN_CARNET"))





class SerieNotionPolling(Serie):
    def __init__(self, id: str, data: dict={}) -> None:
        if not data:
            page: dict = client_notion.pages.retrieve(id)
            data = page['properties']
            
        self.id: str = id
        self.exo: Exercice = self._parse_exo(data)
        self.date: dt = self._parse_date(data)
        self.num: int = int(JsonFile.safe_get(data, "Sets.title.0.plain_text"))
        self.reps: int = int(JsonFile.safe_get(data, "Reps.number"))
        self.poids: float = float(JsonFile.safe_get(data, "Poids.number"))
        self.seance_id: str = JsonFile.safe_get(data, "Weekly Split Schedule.relation.0.id")


    def _parse_exo(self, data: dict) -> Exercice:
        try:
            exo_id = JsonFile.safe_get(data, "Exercise.relation.0.id")
            return ExoDB.get_exo_by_id(exo_id)
        except NotInDBError as e:
            JsonFile.write(data, "error_data.json")
            
        
    def _parse_date(self, data: dict) -> dt:
        date_str = JsonFile.safe_get(data, "Date .date.start")
        return dt.fromisoformat(date_str)

    
    

class SeanceNotionPolling(Seance):
    def __init__(self, id: str, data: dict) -> None:
        self.id: str = id
        self.name: str = JsonFile.safe_get(data, "Name.title.0.plain_text")
        self.body_part: str = JsonFile.safe_get(data, "Body Part.select.name")
        self.date: dt = self._parse_date(data)
        self.content: dict[str, list[Serie]] = self._parse_content(data)
        self.duration: timedelta = self._parse_duration(data)
        
    
    def _parse_date(self, data: dict):
        date_str = JsonFile.safe_get(data, "Date.date.start")
        return dt.fromisoformat(date_str)

    def _parse_content(self, data):
        exos = map(lambda x: ExoDB.get_exo_by_id(x['id']), JsonFile.safe_get(data, "Exercises.relation"))
        series = self._parse_serie(JsonFile.safe_get(data, "Workout Exercises.relation"))
        
        return {
            exo.name: list(filter(lambda serie: serie.exo.name == exo.name, series)) for exo in exos
        }
        
    def _parse_duration(self, data):
        try:
            start = self.date
            end_str = JsonFile.safe_get(data, "Date.date.end")
            end = dt.fromisoformat(end_str)
            return end - start
        except TypeError:
            logger.warning(f"{self.__repr__} has no end date, setting duration to 0.")
            return timedelta(0)

    def _parse_serie(self, ids: list[str]) -> list[Serie]:
        series = []
        
        for e in ids:
            if self.serie_exists(e['id']):
                series.append(SerieDB(e['id']))
            else:
                series.append(SerieNotionPolling(e['id']))
                
        return series

    async def serie_exists(self, id: str) -> bool:
        conn = await aiosqlite.connect(DB_PATH)
        async with conn.execute("SELECT id FROM series WHERE id = ?", (id,)) as cursor:
            res = await cursor.fetchone()
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM series 
                    WHERE exo_id = ?
                )""", (id,))
            
            return cur.fetchone()[0] == 1
    

    def save_seance(self, connection: ConnectionSync) -> None:
        series_ids = []
        logger.info(f"Saving seance: {self.name} - {self.date.date()}")
        for exo, series in self.content.items():
            for serie in series:
                serie.save_to_db(connection=connection)
                series_ids.append(serie.id)
        
        self.save_to_db(connection=connection)
    





class NotionAPI():
    def __init__(self, client: AsyncClient, turso_db: TursoDB) -> None:
        # ExoDB(db_path=DB_PATH,  turso_client=turso_db.conn).sync_from_notion(client_notion=client)
        self.turso_db = turso_db
        self.HISTORY_DS_ID = "5e1bdaf9-cc8d-48b5-ab26-205dcbf47d33"

    async def open_database(self, data_source_id: str="848c44b2-c392-4618-9c5a-a761cd9b81e0") -> AsyncGenerator[dict]:
        """Yields all the children of the page 'ZtH Carnet de bord'"""
        response = await client_notion.data_sources.query(
            data_source_id,
            sorts=[
                {
                    "property": "Date",
                    "direction": "descending"
                }
            ]
        )
        for r in response['results']:
            yield r

        while response.get('has_more'):
            response = await client_notion.data_sources.query(data_source_id, start_cursor=response['next_cursor'])
            for r in response['results']:
                yield r

    
    async def get_seance(self) -> AsyncGenerator[Seance]:
        async for page in self.open_database():
            try:
                seance = SeanceDB(page['id'])
                seance.save_to_db(connection=self.turso_db.conn)
                yield seance
            except NotInDBError:
                yield SeanceNotionPolling(page['id'], page['properties'])
                
    async def get_series(self) -> AsyncGenerator[Serie]:
        async for page in self.open_database():
            try:
                serie = SerieDB(page['id'])
                serie.save_to_db(connection=self.turso_db.conn)
                yield serie
            except NotInDBError:
                yield SerieNotionPolling(page['id'], page['properties'])
                
    async def insert_recent_seance(self) -> None:
        async for page in self.open_database():
            conn = await aiosqlite.connect(DB_PATH)
            res = await conn.execute_fetchall("SELECT id FROM seances WHERE id = ? LIMIT 1", (page['id'],))
            
            if not res:
                seance = SeanceNotionPolling(page['id'], page['properties'])
                seance.save_to_db(connection=self.turso_db.conn)







async def main():
    logger.debug("Starting main function")
    turso_db = TursoDB(
        path=DB_PATH, 
        remote_url=getenv("TURSO_DATABASE_URL"), 
        auth_token=getenv("TURSO_AUTH_TOKEN")
    )
    # init_db(turso_db.conn)
    # turso_db.sync()

    app = NotionAPI(client=client_notion, turso_db=turso_db)
    await app.insert_recent_seance()

    # ic(len(list(app.seances)))


if __name__=='__main__':
    logger.debug("Starting script")
    try:
        asyncio.run(main())
    except (ConnectError, RemoteProtocolError) as e:
        logger.error(f"Problème de connexion à l'API Notion: {e}", exc_info=True)

    logger.debug("Fin du script")
    