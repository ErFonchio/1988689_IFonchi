import psycopg2
from nicegui import ui

ui.label('Fonchi Dashboard')

def get_connection():
    return psycopg2.connect(
        host="127.0.0.1",
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
        "timestamp": str(r[2]),
        "frequency": r[3],
        "amplitude": r[4],
    }
    for r in data
]

table = ui.table(
    columns=[
        {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor'},
        {'name': 'type', 'label': 'Type', 'field': 'type'},
        {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp'},
        {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency'},
        {'name': 'amplitude', 'label': 'Amplitude', 'field': 'amplitude'}
        
    ],
    rows=[]
)

ui.button("Refresh data", on_click=load_data)

ui.run()