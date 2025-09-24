import streamlit as st
import datetime
import plotly.graph_objects as go

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
   
   
def get_workout_week(workout) -> int:
    """Return the week number of a workout.

    Args:
        workout (Workout): Workout object.

    Returns:
        int: Week number.
    """
    pass

def count_streak(workouts) -> int:
    """Count the number of consecutive weeks with at least one workout.

    Args:
        workouts (list): List of Workout objects.

    Returns:
        int: Number of consecutive weeks with at least one workout.
    """
    pass

def weekly_workouts_volume(workouts, week_number) -> float:
    """Calculate the total volume of workouts for a given week.

    Args:
        workouts (list): List of Workout objects.
        week_number (int): Week number.

    Returns:
        float: Total volume of workouts for the week.
    """
    weekly_workouts = filter(lambda w: get_workout_week(w) == datetime.date.today().isocalendar()[1], [])
    return sum(w.duration for w in weekly_workouts)

cols = st.columns(2)
with cols[0]:
    st.write(f"{count_streak([])} Semaines\n")
    st.write("série actuelle")

with cols[1]:
    objectif_minutes = 100
    volume_semaine = weekly_workouts_volume([], datetime.date.today().isocalendar()[1])
    pourcentage = int((volume_semaine / objectif_minutes) * 100) if objectif_minutes else 0
    pourcentage = min(pourcentage, 100)
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = pourcentage,
        number = {'suffix': '%'},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': 'green'},
            'bgcolor': "#e0e0e0",
            'steps': [
                {'range': [0, 100], 'color': '#e0e0e0'}
            ],
        },
        domain = {'x': [0, 1], 'y': [0, 1]}
    ))
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200)
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"{volume_semaine}/100 min")