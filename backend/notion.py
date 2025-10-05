# |-----------Module d'envrionnement---------|
from os import getenv
from os.path import join as pjoin, dirname, abspath
import sys
sys.path.append(abspath(dirname(__file__) + "/.."))
from dotenv import load_dotenv
from pathlib import Path
# |-----------Module pour le projet---------|
from notion_client import Client
from notion_client.errors import HTTPResponseError
from utility import JsonFile
from backend.models import Exercice, Serie, Seance
from backend.models_db import ExoDB, SerieDB, SeanceDB, NotInDBError
from settings.config import DB_PATH
import sqlite3
import json
from datetime import datetime as dt, timedelta
import time
from typing import Generator, Callable
# |-----------Module pour le debug---------|
from icecream import ic
from utility import timer_performance
from logger_config import setup_logger
import logging

logger = setup_logger()





current_folder = Path(__file__).resolve().parent
workspace = current_folder.parent
load_dotenv(dotenv_path=pjoin(workspace, 'settings', '.env'))





NOTION_SECRET = getenv("NOTION_TOKEN_CARNET")
client_notion = Client(auth=NOTION_SECRET)


def safe_request(request: Callable, max_retries: int=5, retry_delay: int=2, *args, **kwargs):
    """Effectue une requête Notion avec retry automatique sur erreurs temporaires."""
    for attempt in range(1, max_retries + 1):
        try:
            return request(*args, **kwargs)

        except HTTPResponseError as e:
            if e.code == "bad_gateway":  # 502
                logger.info(f"[Retry {attempt}/{max_retries}] Erreur 502, nouvel essai dans {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise  # autre erreur : on ne masque pas
    raise RuntimeError(f"Échec après {max_retries} tentatives (erreur 502 persistante).")


class SerieNotion(Serie):
    def __init__(self, id: str) -> None:
        data = safe_request(client_notion.pages.retrieve, page_id=id)['properties']
        self.id: str = id
        self.exo: Exercice = self._parse_exo(data)
        self.date: str = self._parse_date(data)
        self.num: int = int(JsonFile.safe_get(data, "Sets.title.0.plain_text"))
        self.reps: int = int(JsonFile.safe_get(data, "Reps.number"))
        self.poids: float = float(JsonFile.safe_get(data, "Poids.number"))
        self.seance_id: str = JsonFile.safe_get(data, "Weekly Split Schedule.relation.0.id")


    def _parse_exo(self, data: dict) -> Exercice:
        exo_id = JsonFile.safe_get(data, "Exercise.relation.0.id")
        return ExoDB().get_exo_by_id(exo_id)
        
    def _parse_date(self, data: dict) -> dt:
        date_str = JsonFile.safe_get(data, "Date .date.start")
        return dt.fromisoformat(date_str)

    
    

class SeanceNotion(Seance):
    def __init__(self, id: str, data: dict) -> None:
        self.id: str = id
        self.name: str = JsonFile.safe_get(data, "Name.title.0.plain_text")
        self.body_part: str = JsonFile.safe_get(data, "Body Part.select.name")
        self.date: dt = self._parse_date(data)
        self.content: dict[str,list[Serie]] = self._parse_content(data)
        self.duration: timedelta = self._parse_duration(data)
        
        self.save_to_db()
        
    
    def _parse_date(self, data: dict):
        date_str = JsonFile.safe_get(data, "Date.date.start")
        return dt.fromisoformat(date_str)

    def _parse_content(self, data):
        exos = map(lambda x: ExoDB().get_exo_by_id(x['id']), JsonFile.safe_get(data, "Exercises.relation"))
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
                series.append(SerieNotion(e['id']))
                
        return series

    def serie_exists(self, id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM series 
                    WHERE exo_id = ?
                )""", (id,))
            
            return cur.fetchone()[0] == 1
    

    def save_to_db(self) -> None:
        series_ids = []
        for exo, series in self.content.items():
            for serie in series:
                self.save_serie(serie)
                series_ids.append(serie.id)
        
        self.save_seance(series_ids)
        logger.info(f"Saving seance: {self.name} - {self.date.date()}")
    
    def save_serie(self, serie: Serie) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            data_serie = {
                        "id": serie.id,
                        "seance_id": self.id,  # doit exister dans ton objet Seance
                        "num": serie.num,
                        "exo_id": serie.exo.id,
                        "reps": serie.reps,
                        "weight": serie.poids,
                        "date": serie.date.isoformat()
                    }
                        
            cur.execute("""
            INSERT INTO series (id, seance_id, num, exo_id, reps, weight, date)
            VALUES (:id, :seance_id, :num, :exo_id, :reps, :weight, :date)
            ON CONFLICT(seance_id, exo_id, num)
            DO UPDATE SET
                reps=excluded.reps,
                weight=excluded.weight,
                date=excluded.date
        """, data_serie)
    
    def save_seance(self, series_ids: list[str]) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            exo_names = list(self.content.keys())

            cur.execute("""
                INSERT INTO seances (id, name, date, body_part, exo_list, series_list, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    date=excluded.date,
                    body_part=excluded.body_part,
                    exo_list=excluded.exo_list,
                    series_list=excluded.series_list,
                    duration=excluded.duration;
            """, (
                self.id,
                self.name,
                self.date.isoformat(),
                self.body_part,
                json.dumps(exo_names),
                json.dumps(series_ids),
                self.duration.total_seconds(),
            ))







class NotionAPI():
    def __init__(self) -> None:
        ExoDB().sync_from_notion(client_notion)
        self._carnet = self.open_workouts()
        self.seances = self.get_seance()

    def open_workouts(self) -> Generator[dict,any,any]:
        """Yields all the children of the page "ZtH Carnet de bord" (pagination complète, sans fonction annexe)"""
        db_id = "1e522945c40e4c418d5854942b5d4910"
        response = client_notion.databases.query(db_id)
        yield from response['results']

        while response.get('has_more'):
            response = client_notion.databases.query(db_id, start_cursor=response['next_cursor'])
            yield from response['results']
    
    def get_seance(self)->Generator[Seance,any,any]:
        for page in self._carnet:
            try:
                yield SeanceDB(page['id'])
            except NotInDBError:
                yield SeanceNotion(page['id'], page['properties'])

    def update_from_notion():
        pass




notion_logger = logging.getLogger('notion_client')
notion_logger.setLevel(logging.INFO)
notion_logger.handlers.clear()  # Supprime tous les handlers existants
for handler in logger.handlers:
    notion_logger.addHandler(handler)

if __name__=='__main__':
    app = NotionAPI()

    # ic(len(list(app.seances)))

    
    