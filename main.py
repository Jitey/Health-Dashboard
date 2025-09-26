import os
from os import sep
from os.path import join as pjoin
import glob
import streamlit as st
import xml.etree.ElementTree as ET
from utilities import HealthRecord
import pandas as pd
import plotly.express as px
from mylib import timer

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

# Appliquez le gestionnaire personnalisé
formatter = ColoredFormatter(
    fmt='\033[90m\033[1m%(asctime)s\033[0m \033[1m%(levelname)s\033[0m   %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
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




st.sidebar.title("Navigation")
pg = st.navigation(pages, position="sidebar")



pg.run()