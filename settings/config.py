from os.path import join as pjoin
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent

DB_PATH = pjoin(workspace,"data","fitness.sql")
