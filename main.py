import psycopg2
from nicegui import ui

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="FonchiDB",
        user="postgres",
        password="fonchi4ever",
        port=5432
    )

def fetch_events():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT sensor_id, event_type, frequency, amplitude, timestamp
        FROM events
        ORDER BY timestamp DESC
        LIMIT 50;
    """)

    rows = cur.fetchall()

    conn.close()

    return rows

    
ui.label('Fonchi Dashboard')

ui.run()