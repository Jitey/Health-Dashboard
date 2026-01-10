import sqlite3
from notion_client import Client
from utility import JsonFile, timer_performance
from datetime import datetime as dt, timedelta
from .models import Exercice, Serie, Seance, MuscleGroup
from settings.config import DB_PATH, logger
import json

from icecream import ic






class NotInDBError(ValueError):
    """Exception levée lorsqu'une ligne n'existe pas dans la base de données."""
    pass






def init_db(path: str=DB_PATH):
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()

        # Création de la table muscle_groupe
        cur.execute("""
        CREATE TABLE IF NOT EXISTS muscle_group (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            body_part TEXT NOT NULL
        )
        """)

        # Création de la table exercices
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exercices (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            muscle_group TEXT,
            dificulty TEXT,
            FOREIGN KEY (muscle_group) REFERENCES muscle_group(id)
        )
        """)

        # Création de la table seances
        cur.execute("""
        CREATE TABLE IF NOT EXISTS seances (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT,
            date TEXT,
            body_part TEXT,
            exo_list TEXT,
            series_list TEXT,
            duration INTEGER
        )
        """)

        # Création de la table series
        cur.execute("""
        CREATE TABLE IF NOT EXISTS series (
            id TEXT PRIMARY KEY NOT NULL,
            seance_id TEXT NOT NULL,
            num INTEGER,
            exo_id TEXT NOT NULL,
            reps INTEGER,
            weight REAL,
            date TEXT,
            UNIQUE(seance_id, exo_id, num)
            FOREIGN KEY (seance_id) REFERENCES seances(id),
            FOREIGN KEY (exo_id) REFERENCES exercices(id)
        )
        """)
        
        # Création de la table meta 
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            table_name TEXT PRIMARY KEY,
            last_update TEXT
        )
        """)



class ExoDB:
    def __init__(self, db_path=DB_PATH) -> None:
        init_db()
        self.db_path = db_path

    def get_exo_by_name(self, name: str) -> Exercice:
        """Retourne l'exercice par son nom"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, name FROM exercices WHERE name==?", (name,))
            res = cur.fetchone()
            return Exercice(*res)
    
    def get_exo_by_id(self, id: str) -> Exercice:
        """Retourne l'exercice par son ID Notion"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, name FROM exercices WHERE id==?", (id,))
            res = cur.fetchone()
            
            if res is None:
                raise NotInDBError(f"Exercice {id} introuvable en base de données.")
            
            return Exercice(*res)

    
    @timer_performance
    def sync_from_notion(self, client_notion: Client, notion_url: str='026420f9e2b44f2bb72560c9775ac355') -> None:
        """Récupère les nouveaux exercices depuis Notion et insère uniquement ceux qui n'existent pas

        Args:
            client_notion (Client): Client notiob
            notion_url (str, optional): url de la BDD. Defaults to '026420f9e2b44f2bb72560c9775ac355'.
        """
        if self.has_change(client_notion, notion_url):
            logger.info("Exercices are up to date.")
            return

        logger.info("Syncing exercices from Notion...")
        db = client_notion.databases.query(notion_url)
        
        self.fetch(db['results'], client_notion)
        self.upate_date()
            
        logger.info("Exercices database updated.")

    def fetch(self, pages: dict, client_notion: Client) -> None:
        """Fetch the Notion database and update the local database if there are new exercices.

        Args:
            pages (dict): Dictionnaires des exo référencés
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            for page in pages:
                exo = self.retrieve_exos(page, client_notion)
                self.save_exo(cur, exo)
                
                mgs = exo.muscle_group
                self.save_muscle_group(cur, mgs)

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
    
    def save_exo(self, cur: sqlite3.Cursor, exo: Exercice) -> None:
        mg_ids = [group.id for group in exo.muscle_group] if isinstance(exo.muscle_group, list) else exo.muscle_group.id
        cur.execute(
            """INSERT INTO exercices (id, name, muscle_group, dificulty) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    muscle_group=excluded.muscle_group,
                    dificulty=excluded.dificulty;
                """,
            (exo.id, exo.name, json.dumps(mg_ids), exo.difficulty)
        )
    
    def save_muscle_group(self, cur: sqlite3.Cursor, mgs: MuscleGroup|list[MuscleGroup]) -> None:
        if isinstance(mgs, MuscleGroup):
            mgs = [mgs]

        for mg in mgs:
            cur.execute(
                """INSERT INTO muscle_group (id, name, body_part) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        body_part=excluded.body_part;
                    """,
                (mg.id, mg.name, mg.body_part)
            )
        
        
    def has_change(self, client_notion: Client, notion_url: str) -> bool:
        """Check if the Notion database has been updated since the last sync.

        Args:
            client_notion (Client): Client notion

        Returns:
            bool: Booléen indiquant si la DB a changé
        """
        db_header = client_notion.databases.retrieve(notion_url)
        uptdate_date = dt.fromisoformat(db_header['last_edited_time'][:-1])
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
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            for db in ["exercices", "muscle_group"]:
                cur.execute("""
                    INSERT INTO meta (table_name, last_update)
                        VALUES (?, ?)
                        ON CONFLICT(table_name) DO UPDATE SET last_update=excluded.last_update
                    """, 
                    (db, dt.now().isoformat())
                )




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
                raise NotInDBError(f"Groupe musculaire {id} introuvable en base de données.")
        
        self.name = name
        self.body_part = body_part
        
    def __str__(self) -> str:
        return self.name



class ExerciceDB(Exercice):
    def __init__(self, id: str):
        self.id = id
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT name, muscle_group, dificulty
                FROM exercices
                WHERE id = ?
            """, (id,))
            try:
                name, muscle_group_ids, dificulty = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Exercice {id} introuvable en base de données.")
        
        self.name = name
        self.muscle_group = self._parse_muscle_group(muscle_group_ids)
        self.difficulty = dificulty
        
    
    def _parse_muscle_group(self, ids: list[str]) -> list[MuscleGroup]:
        ic(ids)



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
                seance_id, exo_id, num, reps, poids, date = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Série {id} introuvable en base de données.")

        self.seance_id = seance_id
        self.exo = ExoDB().get_exo_by_id(exo_id)
        self.num = num
        self.reps = reps
        self.poids = poids
        self.date = dt.fromisoformat(date)
        
    


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
                name, date, body_part, duration = cur.fetchone()
            except TypeError:
                raise NotInDBError(f"Séance {self.id} introuvable en DB")

            self.name = name
            self.date = dt.fromisoformat(date)
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
        exos = [ExoDB().get_exo_by_id(exo_id) for exo_id in exo_ids]

        # Organiser les séries par exercice
        self.content = {
            exo.name: [s for s in series if s.exo.id == exo.id]
            for exo in exos
        }

