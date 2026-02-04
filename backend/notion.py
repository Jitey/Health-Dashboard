# |-----------Module pour le debug---------|
from icecream import ic
# |-----------Module d'envrionnement---------|
from os import getenv
from os.path import join as pjoin, dirname, abspath
import sys
sys.path.append(abspath(dirname(__file__) + "/.."))
from dotenv import load_dotenv
# |-----------Module pour le projet---------|
from notion_client import Client
from utility import JsonFile
from settings import DB_PATH, workspace, logger
from backend import *
import sqlite3
from datetime import datetime as dt, timedelta
from typing import Iterator
# from flask import Flask, request, Response





load_dotenv(dotenv_path=pjoin(workspace, 'settings', '.env'))





NOTION_SECRET = getenv("NOTION_TOKEN_CARNET")
client_notion = Client(auth=NOTION_SECRET)





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
        
        self.save_to_db()


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
        
        self.save_seance()
        
    
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

    def serie_exists(self, id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM series 
                    WHERE exo_id = ?
                )""", (id,))
            
            return cur.fetchone()[0] == 1
    

    def save_seance(self) -> None:
        series_ids = []
        logger.info(f"Saving seance: {self.name} - {self.date.date()}")
        for exo, series in self.content.items():
            for serie in series:
                serie.save_to_db()
                series_ids.append(serie.id)
        
        self.save_to_db(series_ids)
    





class NotionAPI():
    def __init__(self, client: Client, turso_db: TursoDB) -> None:
        ExoDB(db_path=DB_PATH,  turso_client=turso_db.conn).sync_from_notion(client_notion=client)
        HISTORY_DS_ID = "5e1bdaf9-cc8d-48b5-ab26-205dcbf47d33"
        self._carnet = self.open_database()
        self._history = self.open_database(data_source_id=HISTORY_DS_ID)
        self.seances = self.get_seance()
        self.series = self.get_series()

    def open_database(self, data_source_id: str="848c44b2-c392-4618-9c5a-a761cd9b81e0") -> Iterator[dict]:
        """Yields all the children of the page 'ZtH Carnet de bord'"""
        response = client_notion.data_sources.query(data_source_id)
        yield from response['results']

        while response.get('has_more'):
            response = client_notion.data_sources.query(data_source_id, start_cursor=response['next_cursor'])
            yield from response['results']

    
    def get_seance(self) -> Iterator[Seance]:
        for page in self._carnet:
            try:
                yield SeanceDB(page['id'])
            except NotInDBError:
                yield SeanceNotionPolling(page['id'], page['properties'])
                
    def get_series(self) -> Iterator[Serie]:
        for page in self._history:
            try:
                yield SerieDB(page['id'])
            except NotInDBError:
                yield SerieNotionPolling(page['id'], page['properties'])    







def main():
    turso_db = TursoDB(
        path=DB_PATH, 
        remote_url=getenv("TURSO_DATABASE_URL"), 
        auth_token=getenv("TURSO_AUTH_TOKEN")
    )
    # init_db(turso_db.conn)
    turso_db.sync()

    app = NotionAPI(client=client_notion, turso_db=turso_db)

    # ic(len(list(app.seances)))


if __name__=='__main__':
    try:
        main()
    except (ConnectError, RemoteProtocolError) as e:
        logger.error(f"Problème de connexion à l'API Notion: {e}", exc_info=True)

    ic("Fin du script")
    