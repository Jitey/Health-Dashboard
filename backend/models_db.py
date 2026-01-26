import sqlite3
from notion_client import Client
from utility import JsonFile, timer_performance
from datetime import datetime as dt, timedelta
from .models import Exercice, Serie, Seance, MuscleGroup
from settings import DB_PATH, logger
import json
from turso.sync import ConnectionSync

from icecream import ic






class NotInDBError(ValueError):
    """Exception levée lorsqu'une ligne n'existe pas dans la base de données."""
    pass






def init_db(conn: ConnectionSync) -> None:
    # Création de la table muscle_groupe
    conn.execute("""
    CREATE TABLE IF NOT EXISTS muscle_group (
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        body_part TEXT NOT NULL
    )
    """)

    # Création de la table exercices
    conn.execute("""
    CREATE TABLE IF NOT EXISTS exercices (
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL UNIQUE,
        dificulty TEXT NOT NULL CHECK (dificulty IN ('easy', 'medium', 'hard')),
    )
    """)
    
    # Création de la table de liaison exercices muscle_group    
    conn.execute("""
    CREATE TABLE exercice_muscle_group (
        exercice_id TEXT NOT NULL,
        muscle_group_id TEXT NOT NULL,
        target INTEGER NOT NULL CHECK (target BETWEEN 1 AND 10),
        PRIMARY KEY (exercice_id, muscle_group_id),
        FOREIGN KEY (exercice_id) REFERENCES exercices(id),
        FOREIGN KEY (muscle_group_id) REFERENCES muscle_group(id)
        ); 
    """)


    # Création de la table seances
    conn.execute("""
    CREATE TABLE IF NOT EXISTS seances (
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT,
        date_ts INTEGER NOT NULL,
        body_part TEXT NOT NULL CHECK (body_part IN ('Upper Body', 'Lower Body', 'Full Body')),
        duration INTEGER
    )
    """)

    # Création de la table series
    conn.execute("""
    CREATE TABLE IF NOT EXISTS series (
        id TEXT PRIMARY KEY NOT NULL,
        seance_id TEXT NOT NULL,
        num INTEGER NOT NULL,
        exo_id TEXT NOT NULL,
        reps INTEGER NOT NULL,
        weight REAL NOT NULL,
        date_ts INTEGER NOT NULL,
        UNIQUE(seance_id, exo_id, num)
        FOREIGN KEY (seance_id) REFERENCES seances(id),
        FOREIGN KEY (exo_id) REFERENCES exercices(id)
    )
    """)
    
    # Création de la table meta 
    conn.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        table_name TEXT PRIMARY KEY,
        last_update TEXT
    )
    """)
    
    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_emg_muscle
        ON exercice_muscle_group(muscle_group_id);
    """)
    
    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_seances_date
        ON seances(date_ts);
    """)
    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_series_date
        ON series(date_ts);
    """)
    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_series_seance
        ON series (seance_id);
    """)

    conn.execute("""
    CREATE VIEW IF NOT EXISTS seances_human AS
    SELECT
        id,
        name,
        datetime(date_ts, 'unixepoch') AS date,
        body_part,
        duration
        FROM seances; 
    """)
    conn.execute("""
    CREATE VIEW IF NOT EXISTS series_human AS
    SELECT
        id,
        seance_id,
        num,
        exo_id,
        reps,
        weight,
        datetime(date_ts, 'unixepoch') AS date
    FROM series;
    """)



class ExoDB:
    def __init__(self, db_path, turso_client: ConnectionSync) -> None:
        self.db_path = db_path
        self.turso_client = turso_client

    @staticmethod
    def get_exo_by_name(name: str, db_path: str=DB_PATH) -> Exercice:
        """Retourne l'exercice par son nom"""
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, name FROM exercices WHERE name==?", (name,))
            res = cur.fetchone()
            return Exercice(*res)
    
    @staticmethod
    def get_exo_by_id(id: str, db_path: str=DB_PATH) -> Exercice:
        """Retourne l'exercice par son ID Notion"""
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, name FROM exercices WHERE id==?", (id,))
            res = cur.fetchone()
            
            if res is None:
                raise NotInDBError(f"Exercice {id} introuvable en base de données.\nnotion.so/{id.replace('-', '')}")
            
            return Exercice(*res)

    
    @timer_performance
    def sync_from_notion(self, client_notion: Client, notion_url: str='026420f9e2b44f2bb72560c9775ac355') -> None:
        """Récupère les nouveaux exercices depuis Notion et insère uniquement ceux qui n'existent pas

        Args:
            client_notion (Client): Client notion
            notion_url (str, optional): url de la BDD. Defaults to '026420f9e2b44f2bb72560c9775ac355'.
        """
        if self.has_change(client_notion, notion_url):
            logger.info("Exercices are up to date.")
            return

        logger.info("Syncing exercices from Notion...")
        db = client_notion.databases.query(notion_url)
        
        self.fetch(db['results'], client_notion)
        self.upate_date()
            
        self.turso_client.push()
        logger.info("Exercices database updated.")

    def fetch(self, pages: dict, client_notion: Client) -> None:
        """Fetch the Notion database and update the local database if there are new exercices.

        Args:
            pages (dict): Dictionnaires des exo référencés
        """
        for page in pages:
            exo = self.retrieve_exos(page, client_notion)
            self.save_exo(exo)
            
            mgs = exo.muscle_group
            self.save_muscle_group(mgs)

            logger.info(f"New exercice added: {exo.name} - {id}")

    def retrieve_exos(self, page: dict, client_notion: Client) -> Exercice:
        id = JsonFile.safe_get(page, "id")
        name = JsonFile.safe_get(page, "properties.Name.title.0.plain_text")
        muscle_group_ids = JsonFile.safe_get(page, "properties.Muscle Group.relation")
        muscle_group = [self.retrieve_muscle_group(relation['id'], client_notion) for relation in muscle_group_ids]
        difficulty = JsonFile.safe_get(page, "properties.Difficulty.select.name")

        return Exercice(id, name, muscle_group, difficulty)
 
    def retrieve_muscle_group(self, id: str, client_notion: Client) -> MuscleGroup:
        page = client_notion.pages.retrieve(id)
        name = JsonFile.safe_get(page, "properties.Name.title.0.plain_text")
        body_part = JsonFile.safe_get(page, "properties.Body Part.select.name")
        
        return MuscleGroup(id, name, body_part)
    
    def save_exo(self, exo: Exercice) -> None:
        mg_ids = [group.id for group in exo.muscle_group] if isinstance(exo.muscle_group, list) else exo.muscle_group.id
        self.turso_client.execute(
            """INSERT INTO exercices (id, name, muscle_group, dificulty) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    muscle_group=excluded.muscle_group,
                    dificulty=excluded.dificulty;
                """,
            (exo.id, exo.name, json.dumps(mg_ids), exo.difficulty)
        )
        self.turso_client.commit()
        self.logger.info(f"Exercice saved: {exo.name} - {exo.id}")
    
    def save_muscle_group(self, mgs: MuscleGroup|list[MuscleGroup]) -> None:
        if isinstance(mgs, MuscleGroup):
            mgs = [mgs]

        for mg in mgs:
            self.turso_client.execute(
                """INSERT INTO muscle_group (id, name, body_part) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        body_part=excluded.body_part;
                    """,
                (mg.id, mg.name, mg.body_part)
            )
            self.turso_client.commit()
            self.logger.info(f"Muscle group saved: {mg.name} - {mg.id}")
        
        
    def has_change(self, client_notion: Client, notion_url: str) -> bool:
        """Check if the Notion database has been updated since the last sync.

        Args:
            client_notion (Client): Client notion

        Returns:
            bool: Booléen indiquant si la DB a changé
        """
        db_header = client_notion.databases.retrieve(notion_url)
        uptdate_date = dt.fromisoformat(db_header['last_edited_time'].replace("Z", "+00:00"))
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT last_update FROM meta WHERE table_name=?", ("exercices",))
            try:
                date, = cur.fetchone()
            except TypeError:
                return True

            local_last_update = dt.fromisoformat(date)
        
        return local_last_update < uptdate_date

    def upate_date(self) -> None:
        for db in ["exercices", "muscle_group"]:
            self.turso_client.execute("""
                INSERT INTO meta (table_name, last_update)
                    VALUES (?, ?)
                    ON CONFLICT(table_name) DO UPDATE SET last_update=excluded.last_update
                """, 
                (db, dt.now().isoformat())
            )
        self.turso_client.commit()




class MuscleGroupDB(MuscleGroup):
    def __init__(self, id: str):
        self.id = id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT name, body_part
                FROM muscle_group
                WHERE id = ?
            """, (id,))
            try:
                name, body_part = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Groupe musculaire {id} introuvable en base de données.\nnotion.so/{id.replace('-', '')}")
        
        self.name = name
        self.body_part = body_part



class ExerciceDB(Exercice):
    def __init__(self, id: str):
        self.id = id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT name, dificulty
                FROM exercices
                WHERE id = ?
            """, (id,))
            try:
                name, dificulty = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Exercice {id} introuvable en base de données.\nnotion.so/{id.replace('-', '')}")
        
        self.name = name
        self.muscle_group = self._parse_muscle_group(id)
        self.difficulty = dificulty
        
    
    def _parse_muscle_group(self, ids: list[str]) -> list[MuscleGroup]:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT muscle_group_id
                FROM exercice_muscle_group
                WHERE exercice_id = ?
            """, (self.id,))
            mg_ids = [mg_id for mg_id, in cur.fetchall()]

        return [MuscleGroupDB(mg_id) for mg_id in mg_ids]



class SerieDB(Serie):
    def __init__(self, id: str, *args, **kwargs) -> None:
        self.id = id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT seance_id, exo_id, num, reps, weight, date
                FROM series
                WHERE id = ?
            """, (id,))
            try:
                seance_id, exo_id, num, reps, poids, date_ts = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Série {id} introuvable en base de données.\nnotion.so/{id.replace('-', '')}")

        self.seance_id = seance_id
        self.exo = ExoDB.get_exo_by_id(exo_id)
        self.num = num
        self.reps = reps
        self.poids = poids
        self.date = dt.fromtimestamp(date_ts)
        
    


class SeanceDB(Seance):
    def __init__(self, id: str, *args, **kwargs) -> None:
        self.id = id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT name, date, body_part, duration
                FROM seances
                WHERE id = ?
            """, (self.id,))
            try:
                name, date_ts, body_part, duration = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Séance {self.id} introuvable en DB\nnotion.so/{self.id.replace('-', '')}")

            self.name = name
            self.date = dt.fromtimestamp(date_ts)
            self.body_part = body_part
            self.duration = timedelta(seconds=duration)  # si duration stockée en sec
            self.content = self._parse_content()
            

    def _parse_content(self):
        """Récupère les séries associées à la séance et les organise par exercice."""
        
        # Récupérer les IDs des séries associées à la séance
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                    SELECT id FROM series
                    WHERE seance_id = ?
                    ORDER BY num ASC
                """, (self.id,))
            series_ids = [id for id, in cur.fetchall()]

        # Créer les objets SerieDB pour chaque série
        series = [SerieDB(sid) for sid in series_ids]

        # Récupérer les exercices associés aux séries
        exo_ids = set(s.exo.id for s in series)
        exos = [ExoDB.get_exo_by_id(id=exo_id) for exo_id in exo_ids]

        # Organiser les séries par exercice
        self.content = {
            exo.name: [s for s in series if s.exo.id == exo.id]
            for exo in exos
        }

