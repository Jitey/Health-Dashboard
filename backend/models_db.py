import sqlite3
from pathlib import Path
from os.path import join as pjoin
from notion_client import Client
from utility import JsonFile
from datetime import datetime as dt, timedelta
from utility import timer_performance
from .models import Exercice, Serie, Seance
from settings.config import DB_PATH
from logger_config import setup_logger

from icecream import ic


current_folder = Path(__file__).resolve().parent
workspace = current_folder.parent


logger = setup_logger()



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
            name TEXT NOT NULL
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
            return Exercice(*res)

    
    @timer_performance
    def sync_from_notion(self, client_notion: Client, notion_url: str='026420f9e2b44f2bb72560c9775ac355') -> None:
        """Récupère les nouveaux exercices depuis Notion et insère uniquement ceux qui n'existent pas

        Args:
            client_notion (Client): Client notiob
            notion_url (str, optional): url de la BDD. Defaults to '026420f9e2b44f2bb72560c9775ac355'.
        """
        if not self.has_change(client_notion, notion_url):
            logger.info("Exercices are up to date.")
            return

        
        logger.info("Syncing exercices from Notion...")
        db = client_notion.databases.query(notion_url)
        
        self.fetch(db['results'])
        
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO meta (table_name, last_update)
                    VALUES (?, ?)
                    ON CONFLICT(table_name) DO UPDATE SET last_update=excluded.last_update
                """, 
                ("exercices", dt.now().isoformat())
            )
            
        logger.info("Exercices database updated.")

    def fetch(self, pages: dict) -> None:
        """Fetch the Notion database and update the local database if there are new exercices.

        Args:
            pages (dict): Dictionnaires des exo référencés
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            for page in pages:
                id = JsonFile.safe_get(page, "id")
                name = JsonFile.safe_get(page, "properties.Name.title.0.plain_text")
                muscle_group = JsonFile.safe_get(page, "properties.Muscle Group.relation.0.id")
                difficulty = JsonFile.safe_get(page, "properties.Difficulty.select.name")

                cur.execute("SELECT 1 FROM exercices WHERE id = ?", (id,))

                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO exercices (id, name, muscle_group, dificulty) VALUES (?, ?, ?, ?)",
                        (id, name, muscle_group, difficulty)
                    )

                    logger.info(f"New exercice added: {name} - {id}")
 
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



class SerieDB(Serie):
    def __init__(self, id: str, *args, **kwargs) -> None:
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
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                    SELECT id FROM series
                    WHERE seance_id = ?
                    ORDER BY num ASC
                """, (self.id,))
            series_ids = [id for id, in cur.fetchall()]

        series = [SerieDB(sid) for sid in series_ids]

        exo_ids = set(s.exo.id for s in series)
        exos = [ExoDB().get_exo_by_id(exo_id) for exo_id in exo_ids]

        self.content = {
            exo.name: [s for s in series if s.exo.id == exo.id]
            for exo in exos
        }

