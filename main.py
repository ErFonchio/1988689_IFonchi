import psycopg2
from nicegui import ui

ui.label('Fonchi Dashboard')

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
        SELECT sensor_id, event_type, timestamp, frequency, amplitude 
        FROM events
        ORDER BY timestamp DESC
        LIMIT 50;
    """)

    rows = cur.fetchall()

    conn.close()

    return rows

def load_data():
    data = fetch_events()

    table.rows = [
        {
            "sensor": r[0],
            "type": r[1],
            "frequency": r[2],
            "amplitude": r[3],
            "timestamp": str(r[4]),
        }
        for r in data
    ]

table = ui.table(
    columns=[
        {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor'},
        {'name': 'type', 'label': 'Type', 'field': 'type'},
        {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency'},
        {'name': 'amplitude', 'label': 'Amplitude', 'field': 'amplitude'},
        {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp'},
    ],
    rows=[]
)

ui.button("Refresh data", on_click=load_data)

ui.run()