import streamlit as st
import sqlite3
from settings import DB_PATH
import pandas as pd
import plotly.graph_objects as go
from numpy import cos, pi

st.title("Flux")
st.write("Consultez le flux de vos entraînements.")


db = sqlite3.connect(DB_PATH)
cursor = db.cursor()


df = pd.read_sql_query("""
    SELECT e.name AS Exercise, s.num AS "Set Number", s.reps AS Reps, s.weight AS Weight, s.date_ts AS Date
    FROM series AS s
    JOIN exercices AS e 
        ON s.exo_id = e.id
    WHERE e.name = "Développé Couché"
    ORDER BY s.date_ts DESC
""", db)
df['Date'] = pd.to_datetime(df['Date'], utc=True)


def volume(poids, reps):
    return poids * reps


def phi(poids, reps, rep_max=6, rep_min=4):
    return (1 - cos(pi * (reps - rep_min) / (rep_max - rep_min)))/2

def score(poids, reps, eps=0.07):
    return poids * (1 - eps*phi(poids, reps))

st.dataframe(df)


st.write("### Volume par série")
df['Volume'] = df.apply(lambda row: volume(row['Weight'], row['Reps']), axis=1)
df['Score'] = df.apply(lambda row: score(row['Weight'], row['Reps']), axis=1)

fig = go.Figure(data=go.Scatter(
    x=df['Date'],
    y=df['Volume'],))
st.plotly_chart(fig, use_container_width=True)


st.write("### Score par série")
fig2 = go.Figure(data=go.Scatter(
    x=df['Date'],
    y=df['Score'],))
st.plotly_chart(fig2, use_container_width=True)
