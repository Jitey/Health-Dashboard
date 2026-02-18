from datetime import datetime as dt, timedelta
from turso.sync import ConnectionSync
from settings import DB_PATH, logger


class MissingDataError(Exception):
    """"Exception levée lorsqu'une donnée requise est manquante."""
    pass


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
        
    def save_to_db(self, connection: ConnectionSync) -> None:
        cur = connection.cursor()
    
        # try:            
        cur.execute("""
            INSERT INTO series (id, seance_id, num, exo_id, reps, weight, date_ts)
            VALUES (:id, :seance_id, :num, :exo_id, :reps, :weight, :date_ts)
            ON CONFLICT(seance_id, exo_id, num)
            DO UPDATE SET
                reps=excluded.reps,
                weight=excluded.weight,
                date_ts=excluded.date_ts
        """, {
            "id": self.id,
            "seance_id": self.seance_id,
            "num": self.num,
            "exo_id": self.exo.id,
            "reps": self.reps,
            "weight": self.poids,
            "date_ts": self.date.timestamp()
        })
        
        logger.info(f"Serie {self.num}: {self.exo.name} - {self.date.date()} saved.")
        # except sqlite3.ProgrammingError as e:
        #     if "parameter 2" in str(e):
        #         raise MissingDataError(f"No seance associated with serie {self.num}: {self.exo.name} - {self.date.date()}. \nError: {e}")
        #     else:
        #         raise e
            
        # except sqlite3.IntegrityError as e:
        #     if str(e) == "UNIQUE constraint failed":
        #         logger.info(f"Serie {self.num}: {self.exo.name} - {self.date.date()} already up to date.")
        #     else:
        #         raise e



class Seance():
    def __init__(self, id: str=None, name: str=None, body_part: str=None, date: dt=None, content={}, duration: timedelta=None) -> None:
        self.id: str = id
        self.name: str = name
        self.body_part: str = body_part
        self.date: dt = date
        self.content: dict[str,list[Serie]] = content
        self.duration: timedelta = duration
 
        
    def __hash__(self):
        return hash(self.id)
            
    def __str__(self):
        return f"{self.name} - {self.date}"

    def __repr__(self):
        return f"Seance: {self.name} - Date: {self.date} - ID: {self.id}"

    def save_to_db(self, connection: ConnectionSync) -> None:
        cur = connection.cursor()

        cur.execute("""
            INSERT INTO seances (id, name, date_ts, body_part, duration)
            VALUES (:id, :name, :date_ts, :body_part, :duration)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                date_ts=excluded.date_ts,
                body_part=excluded.body_part,
                duration=excluded.duration;
        """, {
            "id": self.id,
            "name": self.name,
            "date_ts": self.date.timestamp(),
            "body_part": self.body_part,
            "duration": self.duration.total_seconds(),
        })
        
        logger.info(f"Seance: {self.name} - {self.date.date()} saved.")