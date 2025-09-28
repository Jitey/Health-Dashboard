from os import sep
from os.path import join as pjoin
import streamlit as st


from icecream import ic
import logging

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[92m",  # Vert
        "INFO": "\033[94m",   # Bleu
        "WARNING": "\033[93m",  # Jaune
        "ERROR": "\033[91m",  # Rouge
        "CRITICAL": "\033[95m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

dateformat='%Y-%m-%d %H:%M:%S'

consol_handler = logging.StreamHandler()
consol_handler.setFormatter(ColoredFormatter(
    fmt='\033[90m\033[1m%(asctime)s\033[0m \033[1m%(levelname)s\033[0m   %(message)s',
    datefmt=dateformat
))
file_handler = logging.FileHandler('logs.log')
file_handler.setFormatter(logging.Formatter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',
    datefmt=dateformat
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, consol_handler],
)






pages = {
    "Acceuil": [
        st.Page(pjoin("pages", "accueil.py"), title="Bienvenue"),
    ],
    "Sport": [
        st.Page(pjoin("pages", "entrainement.py"), title="Entraînement"),
        st.Page(pjoin("pages", "flux.py"), title="Flux"),
        st.Page(pjoin("pages", "tendance.py"), title="Tendances"),
    ],
}




pg = st.navigation(pages, position="sidebar")



pg.run()