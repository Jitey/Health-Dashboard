from datetime import datetime as dt, timedelta
import pandas as pd
import sqlite3
import json
from settings.config import DB_PATH



class MuscleGroup():
    def __init__(self, id: str, name: str, body_part: str) -> None:
        self.id = id
        self.name = name
        self.body_part = body_part
        
    
    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return f"MuscleGroup(id={self.id}, name={self.name}, body_part={self.body_part})"

    def __hash__(self):
        return hash(self.id)



class Exercice():
    def __init__(self, id: str, name: str, muscle_group: list[MuscleGroup]=None, difficulty: str=None) -> None:
        self.id: str = id
        self.name: str = name
        self.muscle_group = muscle_group
        self.difficulty = difficulty

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
        
    def save_to_db(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            data_serie = {
                        "id": self.id,
                        "seance_id": self.seance_id,
                        "num": self.num,
                        "exo_id": self.exo.id,
                        "reps": self.reps,
                        "weight": self.poids,
                        "date": self.date.isoformat()
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

    def save_to_db(self, series_ids: list[str]) -> None:
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