import psycopg2
from nicegui import ui

ui.label('Fonchi Dashboard').classes('text-3xl font-bold mt-6 mb-4')

all_rows = []


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


def apply_filters():
    sensor_query = ''
    if sensor_filter.value and sensor_filter.value != 'All sensors':
        sensor_query = sensor_filter.value.lower().strip()

    filtered = [
        row for row in all_rows
        if not sensor_query or sensor_query in str(row['sensor']).lower()
    ]

    table.rows = filtered


def load_data():
    global all_rows
    data = fetch_events()
    all_rows = [
        {
            'sensor': r[0],
            'type': r[1],
            'timestamp': str(r[2]),
            'frequency': r[3],
            'amplitude': r[4],
        }
        for r in data
    ]
    apply_filters()


with ui.card().classes('w-full max-w-6xl mx-auto p-4 shadow-lg'):
    ui.markdown('## Recent Events').classes('mb-3')

    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]
    with ui.row().classes('items-center gap-3 flex-wrap mb-4'):
        ui.markdown('**Sensor filtering**').classes('text-sm font-semibold whitespace-nowrap')
        sensor_filter = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('flex1')


    sensor_filter.on('update:modelValue', lambda e: apply_filters())

    table = ui.table(
        columns=[
            {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
            {'name': 'type', 'label': 'Type', 'field': 'type', 'sortable': True},
            {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'sortable': True},
            {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
            {'name': 'amplitude', 'label': 'Amplitude', 'field': 'amplitude', 'sortable': True},
        ],
        rows=[],
        row_key='timestamp',
    ).classes('w-full')

    with ui.row().classes('items-center justify-between gap-2 mt-4'):
        ui.button('Refresh data', on_click=load_data).props('color=primary glossy')


load_data()
#ui.timer(10.0, load_data)

ui.run()