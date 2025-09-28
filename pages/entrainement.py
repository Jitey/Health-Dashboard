import streamlit as st
import datetime
import plotly.graph_objects as go
from backend.notion import NontionAPI, Seance, EXO_BDD

from icecream import ic
import logging
from typing import Generator, Iterable


workouts: Generator[Seance] = NontionAPI().seances


st.set_page_config(page_title="Entrainements", page_icon="", layout="centered")

st.title("Gérer les entrainements [ici](https://www.notion.so/ZERO-TO-HERO-f0d0fe73cbc141cd94998401a8f22e77?source=copy_link)")


# Obtenir la date d'aujourd'hui et le début de la semaine (lundi)
days_number = 7
today = datetime.date.today()
start_of_week = today - datetime.timedelta(days=today.weekday())
days = [start_of_week + datetime.timedelta(days=i) for i in range(days_number)]

cols = st.columns(days_number)
for i, day in enumerate(days):
	with cols[i]:
		if day == today:
			st.success(f"**{day.strftime('%a')}**\n" + day.strftime('%d/%m'))
		else:
			st.info(f"**{day.strftime('%a')}**\n" + day.strftime('%d/%m'))
   
   
def get_workout_week(workout: Seance) -> int:
    """Return the week number of a workout.

    Args:
        workout (Workout): Workout object.

    Returns:
        int: Week number.
    """
    return workout.date.isocalendar()[1]

def count_streak(workouts: Iterable[Seance]) -> int:
    """Count the number of consecutive weeks with at least one workout.

    Args:
        workouts (list): List of Workout objects.

    Returns:
        int: Number of consecutive weeks with at least one workout.
    """
    history = list(workouts)
    streak_count = 0
    current_week = datetime.date.today().isocalendar()[1]
    for workout in history:
        workout_week = get_workout_week(workout)
        if workout_week == current_week:
            streak_count += 1
            current_week -= 1
        elif workout_week < current_week:
            break
        
    return streak_count
    

def weekly_workouts_volume(workouts: Iterable[Seance], date: datetime.date) -> int:
    """Calculate the total volume of workouts for a given week.

    Args:
        workouts (list): List of Workout objects.
        week_number (int): Week number.

    Returns:
        float: Total volume of workouts for the week.
    """
    weekly_workouts: filter[Seance] = filter(lambda w: get_workout_week(w) == date.isocalendar()[1] 
                                                    and w.date.year == date.year, workouts
                                        )
    return sum([w.duration.seconds for w in weekly_workouts])//60




cols = st.columns(2)
with cols[0]:
    st.write(f"{count_streak(workouts)} Semaines\n")
    st.write("série actuelle")

with cols[1]:
    objectif_minutes = 3*50
    volume_semaine = weekly_workouts_volume(workouts, datetime.date.today())
    # volume_semaine = 103
    pourcentage = int((volume_semaine / objectif_minutes) * 100) if objectif_minutes else 0
    pourcentage = min(pourcentage, 100)
    st.progress(pourcentage, text=f"{volume_semaine}/{objectif_minutes} minutes")
