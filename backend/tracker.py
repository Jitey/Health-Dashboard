# |-----------Module d'envrionnement---------|
from os import getenv
from dotenv import load_dotenv
from pathlib import Path
# |-----------Module pour le projet---------|
from notion_client import Client
from notion_client.errors import RequestTimeoutError
from utility import *
import pandas as pd
from datetime import datetime as dt
import json
from typing import Generator
# |-----------Module pour le debug---------|
from icecream import ic
from mylib.timer import timer_performance, cls_timer_performance


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

workspace = Path(__file__).resolve().parent
load_dotenv(dotenv_path=f'{workspace}/.env')






client_notion = Client(auth=getenv("NOTION_TOKEN_CARNET"))       


class ExoBDD():
    """Class to manage the local exercice database and sync it with the Notion database."""
    def __init__(self) -> None:
        self.notion_url = '026420f9e2b44f2bb72560c9775ac355'
        self.notion_id = '07d589bc-40a1-43be-bcb7-b95f151e6c36'
        self.local_bdd = JsonFile.read(f'{workspace}/exo_bdd')
        self.sync()

    
    def has_change(self):
        """Check if the Notion database has been updated since the last sync."""
        db_header = client_notion.databases.retrieve(self.notion_url)
        uptdate_date = dt.fromisoformat(db_header['last_edited_time'][:-1])
        
        return dt.fromisoformat(self.local_bdd['last_update']) < uptdate_date
     
    def fetch(self, db: dict) -> dict[str, str]:
        """Fetch the Notion database and update the local database if there are new exercices."""
        relation_id = self.local_bdd['relation_id']
        relation_exo = self.local_bdd['relation_exo']
        
        for page in db['results']:
            id = JsonFile.safe_get(page, "id")
            name = JsonFile.safe_get(page, "properties.Name.title.0.plain_text")

            if id not in relation_exo:
                relation_id[name] = id
                relation_exo[id] = name
                logging.info(f"New exercice added: {name} - {id}")
                
        return {
            'last_update': dt.now().isoformat(timespec="microseconds"),
            'relation_id': relation_id,
            'relation_exo': relation_exo
        }

    def sync(self) -> None:
        """Sync the local database with the Notion database if there are changes."""
        if not self.has_change():
            logging.info("Exercices are up to date.")
            return
        
        logging.info("Syncing exercices from Notion...")
        db = client_notion.databases.query(self.notion_url)
        
        JsonFile.write(self.fetch(db), f'{workspace}/exo_bdd')
        logging.info("Exercices database updated.")




class ExerciceNotion():
    def __init__(self, id: str) ->None:
        self.id: str = id
        self.name: str = EXO_BDD['relation_exo'][id]

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"Exercice: {self.name} - ID: {self.id}"
    
    def __hash__(self):
        return hash(self.id)


class Serie():
    def __init__(self, id: str) -> None:
        self._data = client_notion.pages.retrieve(id)['properties']
        self.exo: ExerciceNotion = ExerciceNotion(JsonFile.safe_get(self._data, "Exercise.relation.0.id"))
        self.date: str = None
        self.num: int = int(JsonFile.safe_get(self._data, "Sets.title.0.plain_text"))
        self.reps: int = int(JsonFile.safe_get(self._data, "Reps.number"))
        self.poids: float = float(JsonFile.safe_get(self._data, "Poids.number"))
        
    @property
    def date(self)->str:
        return self.__date
    @date.setter
    def date(self, date):
        date_str = JsonFile.safe_get(self._data, "Date .date.start")
        self.__date = dt.fromisoformat(date_str)
        

    def __repr__(self):
        return f"Série {self.num}: {self.reps} reps - {self.poids} kg"
    
    def __lt__(self, other):
        return self.num < other.num
    
    def __hash__(self):
        return hash((self.exo, self.date))



# class Exercice():
#     def __init__(self, id: str) ->None:
#         self.data = client_notion.pages.retrieve(id)['properties']
#         ic(self.data)
#         self.name: str = RELATION_EXO[id]
#         self.date: str = None
#         self.series: list[Serie] = data
    
    
#     @property
#     def date(self)->str:
#         return self.__date
#     @date.setter
#     def date(self, date):
#         date_str = JsonFile.safe_get(self.data, "Date.date.start")
#         self.__date = dt.fromisoformat(date_str)
    
    
#     @property
#     def series(self):
#         return self.__series
    
#     @series.setter
#     def series(self, data: dict)->list[Serie]:
#         if self.date:
#             self.__series = [
#                 Serie(1,JsonFile.safe_get(data, "Série 1.rich_text.0.plain_text").split('x')),
#                 Serie(2,JsonFile.safe_get(data, "Série 2.rich_text.0.plain_text").split('x')),
#                 Serie(3,JsonFile.safe_get(data, "Série 3.rich_text.0.plain_text").split('x'))
#             ]
    
        
#     def to_dict(self)->dict:
#         return {
#             'Name': self.name,
#             'Date': self.date,
#             'Serie': self.series
#         }
    
#     def __repr__(self) -> str:
#         return f"Exercice: {self.name} - Date: {self.date}\n" + \
#                '\n'.join([str(serie) for serie in self.series])




class Seance():
    def __init__(self, data: dict) -> None:
        self._data = data
        self.name: str = JsonFile.safe_get(self._data, "Name.title.0.plain_text")
        self.body_part: str = JsonFile.safe_get(self._data, "Body Part.select.name")
        self.date: str = None
        self.content: dict[str,ExerciceNotion] = {}
        
    
    @property
    def date(self) -> dt:
        return self.__date
    @date.setter
    def date(self, data: dict):
        date_str = JsonFile.safe_get(self._data, "Date.date.start")
        self.__date = dt.fromisoformat(date_str)

    @property    
    def content(self):
        return self.__content
    @content.setter
    def content(self, data):
        exos = map(lambda x: ExerciceNotion(x['id']), JsonFile.safe_get(self._data, "Exercises.relation"))
        series = [Serie(e['id']) for e in JsonFile.safe_get(self._data, "Workout Exercises.relation")]
        
        self.__content = {
            exo.name: list(filter(lambda serie: serie.exo.name == exo.name, series)) for exo in exos
        }
    
            
    def __str__(self):
        return f"{self.name} - {self.date}"

    def __repr__(self):
        return f"Seance: {self.name} - Date: {self.date}"



class MyApp():
    def __init__(self) -> None:
        self._carnet = self.open_workouts()
        self.seances = self.get_seance()
        
    
             
    def open_workouts(self) -> Generator[dict,any,any]:
        """Yields all the children of the page "ZtH Carnet de bord"

        Yields:
            Generator[dict,any,any]: Each yield is a the page of the database
        """
        yield from client_notion.databases.query("1e522945c40e4c418d5854942b5d4910")['results']


    def get_seance(self)->Generator[Seance,any,any]:
        for page in self._carnet:
            yield Seance(page['properties'])



    

if __name__=='__main__':
    EXO_BDD = ExoBDD().local_bdd
    app = MyApp()
    
    app.get_seance()
    
    seance = next(app.seances)
    ic(seance)
    ic(seance.content)