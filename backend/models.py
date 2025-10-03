from os.path import join as pjoin
from pathlib import Path
from datetime import datetime as dt, timedelta
import pandas as pd
from logger_config import setup_logger

logger = setup_logger()

current_folder = Path(__file__).resolve().parent
workspace = current_folder.parent
DB_PATH = pjoin(workspace,"data","fitness.sql")




class Exercice():
    def __init__(self, id: str, name: str) -> None:
        self.id: str = id
        self.name: str = name

    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return f"Exercice: {self.name} - ID: {self.id}"
    
    def __hash__(self):
        return hash(self.id)




class Serie():
    def __init__(self, id=None, exo: str=None, date: dt=None, num: int=None, reps: int=None, poids: float=None, seance_id: str=None) -> None:
        self.id: str = id
        self.exo: Exercice = exo
        self.date: dt = date
        self.num: int = num
        self.reps: int = reps
        self.poids: float = poids
        self.seance_id: str = seance_id
    

    def __repr__(self):
        return f"Série {self.num}: {self.reps} reps - {self.poids} kg"
    
    def __lt__(self, other):
        return self.num < other.num
    
    def __hash__(self):
        return hash((self.num, self.exo, self.date))
    
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
    def __init__(self, id: str=None, name: str=None, body_part: str=None, date: dt=None, content={}, duration: timedelta=None) -> None:
        self.id: str = id
        self.name: str = name
        self.body_part: str = body_part
        self.date: dt = date
        self.content: dict[str,list[Serie]] = content
        self.duration: timedelta = duration
 
        
    def __hash__(self):
        return hash((self.name, self.date))
            
    def __str__(self):
        return f"{self.name} - {self.date}"

    def __repr__(self):
        return f"Seance: {self.name} - Date: {self.date} - ID: {self.id}"

    def save_as_csv(self) -> None:
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
        
    def load_csv(self) -> pd.DataFrame:
        history = pd.read_csv(pjoin(workspace, 'data', 'history.csv'))
        return history[history['Seance_ID'] == self.id]
