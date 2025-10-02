from os import sep
from os.path import join as pjoin
import streamlit as st


from icecream import ic
from logger_config import setup_logger

logger = setup_logger()






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