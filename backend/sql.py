import sqlite3
from pathlib import Path
from os.path import join as pjoin
from notion_client import Client
from utility import JsonFile
from datetime import datetime as dt
from logger_config import setup_logger

from icecream import ic

DB_PATH = pjoin(Path(__file__).parent.parent,"data","fitness.sql")


logger = setup_logger()



def init_db(path: str=DB_PATH):
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS muscle_group (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS exercices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            muscle_group TEXT,
            dificulty TEXT,
            FOREIGN KEY (muscle_group) REFERENCES muscle_group(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS seances (
            id TEXT PRIMARY KEY,
            date DATE NOT NULL,
            duration REAL,
            nb_exos INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS series (
            id TEXT PRIMARY KEY,
            seance_id TEXT NOT NULL,
            exo_id TEXT NOT NULL,
            reps INTEGER,
            poids REAL,
            FOREIGN KEY (seance_id) REFERENCES seances(id),
            FOREIGN KEY (exo_id) REFERENCES exercices(id)
        )
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            table_name TEXT PRIMARY KEY,
            last_update TEXT
        )
        """)



class ExoDB:
    def __init__(self, db_path=DB_PATH):
        init_db()
        self.db_path = db_path

    def get_exo_by_name(self, name: str) -> dict:
        """Retourne l'exercice par son nom"""
    
    def get_exo_by_id(self, id: str) -> dict:
        """Retourne l'exercice par son ID Notion"""

    
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
            row = cur.fetchone()

            local_last_update = dt.fromisoformat(row[0]) if row[0] else dt.min
        
        return local_last_update < uptdate_date