import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sqlite3
from backend.models_db import DB_PATH, MuscleGroupDB
import json
from logs.logger_config import setup_logger

from icecream import ic


logger = setup_logger()



def load_seance_data() -> pd.DataFrame:
    """Charger les données de la table seances
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql(
            """SELECT w.date, 
                      w.duration, 
                      count(w.series_list) AS total_serie, 
                      SUM(s.reps*s.weight) AS volume,
                      SUM(s.reps) AS total_reps
                FROM seances AS w
                JOIN series AS s ON s.seance_id == w.id
                GROUP BY w.id
                ORDER BY w.date DESC       
            """, conn)

    df['date'] = pd.to_datetime(df['date'], utc=True)
    df["duration"] = pd.to_timedelta(df["duration"], unit="s")

    return df

def load_serie_data() -> pd.DataFrame:
    """Charger les données de la table series
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql(
            """SELECT s.date AS date, 
                      s.num AS num,
                      s.reps AS reps,
                      s.weight AS poids,
                      s.reps*s.weight AS volume,
                      e.name AS exercice,
                      e.muscle_group AS muscle_group
                FROM series AS s
                JOIN exercices AS e ON s.exo_id == e.id
                GROUP BY s.id
                ORDER BY s.date DESC       
            """, conn)
    
    df['muscle_group'] = df['muscle_group'].apply(lambda row: [MuscleGroupDB(id) for id in json.loads(row)])
    df['date'] = pd.to_datetime(df['date'], utc=True, format='ISO8601')

    return df


def get_datat_within_date(df: pd.DataFrame, key=0) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    timezone = df['date'][0].tz
    end_date = pd.Timestamp.today(tz=timezone)
    end = pd.Timestamp.combine(end_date.date(), pd.Timestamp.max.time()).tz_localize(timezone)
    start_date = st.date_input(
        "Depuis le",
        value=end - pd.Timedelta(days=6),
        key=key
    )
    start = pd.Timestamp.combine(start_date, pd.Timestamp.min.time()).tz_localize(timezone)


    return df[df['date'] > start], start, end
        

def graph_time(data: pd.DataFrame):
    df, start, end = get_datat_within_date(data)
    
    total_duration = df["duration"].sum()
    hours, remainder = divmod(total_duration.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    st.info(f"""Temps Total: {int(hours):02d}h{int(minutes):02d}\n
            {start.date().strftime("%d %b")} - {end.date().strftime("%d %b")}
    """)

    # Créer le bar chart
    df['duration'] = df['duration'].dt.total_seconds()/3600
    fig = go.Figure([go.Bar(x=df['date'], y=df['duration'])])
    fig.update_layout(title="Temps total d'heures par jour de la semaine", yaxis_title="Heures", xaxis_title="Jour")

    st.plotly_chart(fig)


def graph_volume(data: pd.DataFrame):
    df, start, end = get_datat_within_date(data)
    
    total_volume = df["volume"].sum()
    
    st.info(f"""Volume Total: {int(total_volume):,}kg\n
            {start.date().strftime("%d %b")} - {end.date().strftime("%d %b")}
    """)

    # Créer le bar chart
    fig = go.Figure([go.Bar(x=df['date'], y=df['volume'])])
    fig.update_layout(title="Volume total de la semaine", yaxis_title="kg", xaxis_title="Jour")

    st.plotly_chart(fig)


def graph_series(data: pd.DataFrame):
    df, start, end = get_datat_within_date(data)
    
    total_serie = df["total_serie"].sum()
    
    st.info(f"""Totla de séries: {int(total_serie)}\n
            {start.date().strftime("%d %b")} - {end.date().strftime("%d %b")}
    """)

    # Créer le bar chart
    fig = go.Figure([go.Bar(x=df['date'], y=df['total_serie'])])
    fig.update_layout(title="Total de séries de la semaine", yaxis_title="kg", xaxis_title="Jour")

    st.plotly_chart(fig)


def graph_choice():
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Temps"):
            st.session_state.graph = "Temps"
            st.rerun()
    with col2:
        if st.button("Volume", key=10):
            st.session_state.graph = "Volume"
            st.rerun()
    with col3:
        if st.button("Séries", key=11):
            st.session_state.graph = "Séries"
            st.rerun()




def stats(data: pd.DataFrame):
    df = get_datat_within_date(data, 1)[0]
    
    col1, col2 = st.columns(2)

    with col1:
        st.success(f"""Entrainements\n 
                   {len(df)}""")
        st.success(f"""Volume soulevé\n 
                   {int(df["volume"].sum())}kg""")
        
    with col2:
        total_duration = df["duration"].sum()
        hours, remainder = divmod(total_duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        st.success(f"""Temps enregistré\n 
                   {int(hours):02d}h{int(minutes):02d}""")
        st.success(f"""Volume soulevé\n 
                   {int(df["total_reps"].sum())}""")




def serie_by_body_part(data: pd.DataFrame) -> pd.Grouper:
    df = get_datat_within_date(data, 2)[0]
    
    df['muscle_group'] = df['muscle_group'].apply(lambda mgs: mgs[0].body_part)
    df_flat = df.explode('muscle_group', ignore_index=True)
    
    return df_flat.groupby('muscle_group')
    
    
def spider_chart(x: pd.Series, y: pd.Series, label: str="") -> None:
    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=x,
        theta=y,
        fill='toself',
        name='Réps',
        text=[f"{r} {label}" for r in x],  # Label sous chaque point
        textposition='bottom center',  # Position du label
        mode='lines+markers+text',
        marker=dict(size=6),
        line=dict(width=2)
    ))

    # Mise en forme
    fig.update_layout(
        template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white",
        polar=dict(
            radialaxis=dict(visible=True, showticklabels=False, showline=False),
            angularaxis=dict(showline=False, tickfont=dict(size=14))  # labels autour
        ),
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)
    

def body_part_reps(data: pd.DataFrame):
    df = serie_by_body_part(data)

    df_grouped = df['reps'].sum().reset_index()
    spider_chart(df_grouped["reps"], df_grouped["muscle_group"])


def body_part_series(data: pd.DataFrame):
    df = serie_by_body_part(data)

    df_grouped = df['num'].sum().reset_index()
    spider_chart(df_grouped["num"], df_grouped["muscle_group"])


def body_part_volume(data: pd.DataFrame):
    df = serie_by_body_part(data)

    df_grouped = df['volume'].sum().reset_index()
    spider_chart(df_grouped["volume"], df_grouped["muscle_group"])


def spider_choice():
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Reps"):
            st.session_state.spider = "Reps"
            st.rerun()
    with col2:
        if st.button("Séries", key=12):
            st.session_state.spider = "Séries"
            st.rerun()
    with col3:
        if st.button("Volume", key=13):
            st.session_state.spider = "Volume"
            st.rerun()







workouts = load_seance_data()
series = load_serie_data()

st.title("Tendances")



st.write("### Progès")

# ---- Valeur par défaut au chargement ----
if "graph" not in st.session_state:
    st.session_state.graph = "Temps"

# ---- Affichage du graphique correspondant ----
match st.session_state.graph:
    case "Temps":
        graph_time(workouts)
    case "Volume":
        graph_volume(workouts)
    case "Séries":
        graph_series(workouts)


graph_choice()



st.write("### Statistiques")

stats(workouts)


st.write("### Groupes Musculaires")


# ---- Valeur par défaut au chargement ----
if "spider" not in st.session_state:
    st.session_state.spider = "Reps"

# ---- Affichage du graphique correspondant ----
match st.session_state.spider:
    case "Reps":
        body_part_reps(series)
    case "Séries":
        body_part_series(series)
    case "Volume":
        body_part_volume(series)


spider_choice()

