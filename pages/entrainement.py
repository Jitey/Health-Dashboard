import streamlit as st
from datetime import datetime as dt, date, timedelta
import plotly.graph_objects as go
from backend.models_db import DB_PATH, SeanceDB
import sqlite3

from icecream import ic
from typing import Generator, Iterable
from utility import timer_performance
from logs.logger_config import setup_logger

logger = setup_logger()




st.set_page_config(page_title="Entrainements", page_icon="", layout="centered")

st.title("Gérer les entrainements [ici](https://www.notion.so/ZERO-TO-HERO-f0d0fe73cbc141cd94998401a8f22e77?source=copy_link)")


DAYS_NUMBER = 7

def open_history() -> list[SeanceDB]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT * from seances
        """)
        
        return [SeanceDB(*args) for args in cur.fetchall()]

def week_calendar() -> None:
    """Créer un calendrier hebdo avec la date d'aujourd'hui surlignée
    """
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    days = [start_of_week + timedelta(days=i) for i in range(DAYS_NUMBER)]

    cols = st.columns(DAYS_NUMBER)
    for i, day in enumerate(days):
        with cols[i]:
            if day == today:
                st.success(f"**{day.strftime('%a')}**\n" + day.strftime('%d/%m'))
            else:
                st.info(f"**{day.strftime('%a')}**\n" + day.strftime('%d/%m'))


   
def group_workout_by_week(workouts: Iterable[SeanceDB]) -> dict:
    """Renvoie la liste des séances sous forme de dictionnaire avec comme clé la semaine et valeurs les séances de la semaines

    Args:
        workouts (Iterable[SeanceDB]): Liste des séances

    Returns:
        dict: Dictionaire des séances rangé par semaines
    """
    weeks = {}
    for workout in workouts:
        year, week, _ = workout.date.isocalendar()
        key = (year, week)
        
        if key not in weeks:
            weeks[key] = set()
            
        weeks[key].add(workout.name)
        
    return weeks

def count_streak(workouts: Iterable[SeanceDB]) -> int:
    """Count the number of consecutive weeks with at least one workout.

    Args:
        workouts (list): List of Workout objects.

    Returns:
        int: Number of consecutive weeks with at least one workout.
    """
    weeks = group_workout_by_week(workouts)
    sorted_weeks = sorted(weeks.keys(), reverse=True)

    required_sessions = {"Upper A", "Lower", "Upper B"}
    streak_count = 0
    current_year, current_week, _ = date.today().isocalendar()
    for year_week in sorted_weeks:
        if year_week == (current_year, current_week) and not required_sessions.issubset(weeks[year_week]):
            continue  # Ignore la semaine actuelle si elle n'est pas terminé
        elif required_sessions.issubset(weeks[year_week]):
            streak_count += 1
        else:
            break
        
    return streak_count

@timer_performance
def week_streak(workouts: Iterable[SeanceDB]) -> None:
    """Affiche la série de semaine consécutive avec 3 entrainements
    """
    st.write(f"{count_streak(workouts)} Semaines\n")
    st.write("série actuelle")


def weekly_workouts_volume(week_date: date=date.today()) -> int:
    """Calculate the total volume of workouts for a given week.

    Args:
        week_date (date): Date to retrieve week from

    Returns:
        float: Total volume of workouts for the week.
    """
    start_of_week = week_date - timedelta(days=week_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT duration FROM seances
            WHERE date BETWEEN ? AND ?
        """, (start_of_week.isoformat(), end_of_week.isoformat()))
        
        total_seconds = sum([duration for duration, in cur.fetchall()])

    return total_seconds // 60

@timer_performance
def week_volume() -> None:
    """Display the weekly volume as a progress bar
    """
    TARGET_MINUTES = 3*50
    volume = weekly_workouts_volume()

    pourcentage = int((volume / TARGET_MINUTES) * 100) if TARGET_MINUTES else 0
    pourcentage = min(pourcentage, 100)

    st.progress(pourcentage, text=f"{volume}/{TARGET_MINUTES} minutes")




WORKOUTS = open_history()

week_calendar()

cols = st.columns(2)
with cols[0]:
    week_streak(WORKOUTS)
with cols[1]:
    week_volume()


