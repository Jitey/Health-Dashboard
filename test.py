import os
from dotenv import load_dotenv
from settings.config import DB_PATH, logger
import turso.sync
import sqlite3
import json
from typing import Iterator
# from backend.models_db import SeanceDB
from utility import timer_performance

from icecream import ic

load_dotenv("./settings/.env")

url = os.getenv("TURSO_DATABASE_URL")
auth_token = os.getenv("TURSO_AUTH_TOKEN")


def sync_turso(databse_path: str, remote_url: str, auth_token: str):
    conn = turso.sync.connect(databse_path, remote_url=remote_url, auth_token=auth_token) 

    changed = conn.pull()
    logger.info(f"Pulled: {changed}")  # True if there were new remote changes
    
    # changed = conn.push()
    # logger.info(f"Pushed: {changed}")  # True if there were local changes to push

    stats = conn.stats()
    logger.info(f"Network received (bytes): {stats.network_received_bytes}")
    # conn.checkpoint()  # compact local WAL after many writes

    conn.close()

# try:
#     sync_turso(DB_PATH, url, auth_token)
# except Exception as e:
#     logger.error(f"Error fetching data from Turso database: {e}")


tables = [
    "seances",
    "exercices",
    "series",
    "muscle_group",
]



# @timer_performance
def parse_seances() -> Iterator:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, series_list, exo_list FROM seances")
        res = cur.fetchall()
        
    for seance_id, series_list_str, exo_list_str in res:
        yield seance_id, json.loads(series_list_str), json.loads(exo_list_str)


def exo_from_series(serie_id: str) -> str:
    with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT exo_id FROM series WHERE id = ?", (serie_id,))
            exo_id, = cursor.fetchone()
            
    return exo_id


@timer_performance
def retrieve_exos(series_list: list[str]):
    exos = []
    for serie_id in series_list:
        try:
            exo_id = exo_from_series(serie_id)
        except Exception as e:
            logger.error(f"Error retrieving exo for serie {serie_id}: {e}")
            # raise e
            
        if exo_id in exos:
            continue
        else:
            exos.append(exo_id)
    
    return seance_id, exos

def update_exo_list_in_seance(seance_id: str, exo_list: list):
    exo_list_str = json.dumps(exo_list)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE seances
            SET exo_list = ?
            WHERE id = ?
        """, (exo_list_str, seance_id))
        
        conn.commit()



if __name__ == "__main__":
    for seance_id, series_list, exo_list in parse_seances():
        exos = retrieve_exos(series_list)
        # ic(exos)
        
        
    ic("Fin du script")