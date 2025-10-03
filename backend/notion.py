# |-----------Module d'envrionnement---------|
from os import getenv
from os.path import join as pjoin, dirname, abspath
import sys
sys.path.append(abspath(dirname(__file__) + "/.."))
from dotenv import load_dotenv
from pathlib import Path
# |-----------Module pour le projet---------|
from notion_client import Client
from utility import JsonFile
from sql import ExoDB
import pandas as pd
from datetime import datetime as dt, timedelta
from typing import Generator
# |-----------Module pour le debug---------|
from icecream import ic
from utility import timer_performance
from logger_config import setup_logger

logger = setup_logger()





current_folder = Path(__file__).resolve().parent
workspace = current_folder.parent
load_dotenv(dotenv_path=pjoin(workspace, 'settings', '.env'))






client_notion = Client(auth=getenv("NOTION_TOKEN_CARNET"))       


class ExoBDD():
    """Class to manage the local exercice database and sync it with the Notion database."""
    def __init__(self) -> None:
        self.notion_url = '026420f9e2b44f2bb72560c9775ac355'
        self.notion_id = '07d589bc-40a1-43be-bcb7-b95f151e6c36'
        self.local_bdd = JsonFile.read(f'{current_folder}/exo_bdd')
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
                logger.info(f"New exercice added: {name} - {id}")
                
        return {
            'last_update': dt.now().isoformat(timespec="microseconds"),
            'relation_id': relation_id,
            'relation_exo': relation_exo
        }

    @timer_performance
    def sync(self) -> None:
        """Sync the local database with the Notion database if there are changes."""
        if not self.has_change():
            logger.info("Exercices are up to date.")
            return
        
        logger.info("Syncing exercices from Notion...")
        db = client_notion.databases.query(self.notion_url)
        
        JsonFile.write(self.fetch(db), f'{current_folder}/exo_bdd')
        logger.info("Exercices database updated.")


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
    def __init__(self) -> None:
        self.id: str = None
        self._data = None
        self.exo: ExerciceNotion = None
        self.date: str = None
        self.num: int = None
        self.reps: int = None
        self.poids: float = None
        self.seance_id: str = None
    

    def __repr__(self):
        return f"Série {self.num}: {self.reps} reps - {self.poids} kg"
    
    def __lt__(self, other):
        return self.num < other.num
    
    def __hash__(self):
        return hash((self.exo, self.date))
    
    def __eq__(self, other):
        return self.exo == other.exo and self.date == other.date and self.num == other.num
    
    def to_df(self)->pd.DataFrame:
        return pd.DataFrame([{
            'ID': self.id,
            'Exercice': self.exo.name,
            'Date': self.date,
            'Série': self.num,
            'Reps': self.reps,
            'Poids': self.poids,
            'Seance_ID': self.seance_id,
            'Exo_ID': self.exo.id,
        }])

class Seance():
    def __init__(self, *args, **kwargs) -> None:
        self.id: str = id
        self.name: str = None
        self.body_part: str = None
        self.date: dt = None
        self.content: dict[str,list[Serie]] = None
        self.duration: timedelta = None

        
            
    def __str__(self):
        return f"{self.name} - {self.date}"

    def __repr__(self):
        return f"Seance: {self.name} - Date: {self.date}"

    def save(self) -> None:
        history = pd.read_csv(pjoin(workspace, 'data', 'history.csv'))
        
        for exo, series in self.content.items():
            for s in series:
                if (s.date, s.num, s.seance_id) not in history.itertuples():
                    row = s.to_df()
                    row['Seance_Name'] = self.name
                    row['Seance_Body_part'] = self.body_part
                    row['Seance_Duration'] = self.duration
                    history = pd.concat([history, row], ignore_index=True)
                
        history.to_csv(pjoin(workspace, 'data', 'history.csv'), index=False)
        logger.info(f"Saving seance: {self.name} - {self.date.date()}")
        
    def load(self) -> pd.DataFrame:
        history = pd.read_csv(pjoin(workspace, 'data', 'history.csv'))
        return history[history['Seance_ID'] == self.id]
    


class SerieNotion(Serie):
    def __init__(self, id: str) -> None:
        data = client_notion.pages.retrieve(id)['properties']
        self.id: str = id
        self.exo: ExerciceNotion = ExerciceNotion(JsonFile.safe_get(data, "Exercise.relation.0.id"))
        self.date: str = self._parse_date(data)
        self.num: int = int(JsonFile.safe_get(data, "Sets.title.0.plain_text"))
        self.reps: int = int(JsonFile.safe_get(data, "Reps.number"))
        self.poids: float = float(JsonFile.safe_get(data, "Poids.number"))
        self.seance_id: str = JsonFile.safe_get(data, "Weekly Split Schedule.relation.0.id")

        
    def _parse_date(self, data: dict):
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
        
        self.save()
        
    
    def _parse_date(self, data: dict):
        date_str = JsonFile.safe_get(data, "Date.date.start")
        return dt.fromisoformat(date_str)

    def _parse_content(self, data):
        exos = map(lambda x: ExerciceNotion(x['id']), JsonFile.safe_get(data, "Exercises.relation"))
        series = [SerieNotion(e['id']) for e in JsonFile.safe_get(data, "Workout Exercises.relation")]
        
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
            logger.warning(f"Seance {self.name} - {self.id} has no end date, setting duration to 0.")
            return timedelta(0)



class SerieCSV(Serie):
    def __init__(self, data: pd.Series) -> None:
        self.id: str = data['ID']
        self.exo: ExerciceNotion = ExerciceNotion(data['Exo_ID'])
        self.date: str = pd.to_datetime(data['Date'])
        self.num: int = int(data['Série'])
        self.reps: int = int(data['Reps'])
        self.poids: float = float(data['Poids'])
        self.seance_id: str = data['Seance_ID']


class SeanceCSV(Seance):
    def __init__(self, data: pd.DataFrame) -> None:
        first_row = data.iloc[0]
        self.id: str = first_row['Seance_ID']
        self.name: str = first_row['Seance_Name']
        self.body_part: str = first_row['Seance_Body_part']
        self.date: dt = pd.to_datetime(first_row['Date'])
        self.content: dict[str,list[Serie]] = data
        self.duration: timedelta = pd.to_timedelta(first_row['Seance_Duration'])


    @property    
    def content(self):
        return self.__content
    @content.setter
    def content(self, data: pd.DataFrame):
        exos = map(lambda id: ExerciceNotion(id), data['Exo_ID'].unique())
        series = [SerieCSV(row) for idx, row in data.iterrows()]
        
        self.__content = {
            exo.name: list(filter(lambda serie: serie.exo.name == exo.name, series)) for exo in exos
        }
        





class NontionAPI():
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
        try:
            history = pd.read_csv(pjoin(workspace, 'data', 'history.csv'))
        except FileNotFoundError:
            history = pd.DataFrame(columns=['ID', 'Exercice', 'Date', 'Série', 'Reps', 'Poids', 'Seance_ID'])

        for page in self._carnet:
            if page['id'] in history['Seance_ID'].values:
                yield SeanceCSV(history[history['Seance_ID'] == page['id']])
            else:
                yield SeanceNotion(page['id'], page['properties'])

    @timer_performance
    def save_all_seance(self) -> None:
        for seance in self.seances:
            if isinstance(seance, SeanceNotion):
                logger.info(f"Saving seance: {seance.name} - {seance.date.date()}")
                seance.save()


    

EXO_BDD = ExoBDD().local_bdd
if __name__=='__main__':
    app = NontionAPI()
    
    # ic(len(list(app.seances)))
    app.save_all_seance()
    
    # app.save_all_seance()