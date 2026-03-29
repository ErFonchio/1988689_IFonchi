import psycopg2
from nicegui import ui

ui.add_head_html('''
    <style>
        html, body {
            background-color: #0f172a;
        }
    </style>
''')

ui.label('Fonchi Dashboard').classes('text-3xl font-bold mt-6 mb-4 text-white')

all_rows = []
event_tables = []
event_labels = []
event_table_keys = ['earthquake', 'conventional_explosion', 'nuclear_like']
event_table_titles = ['earthquake', 'conventional explosion', 'nuclear like']


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

    grouped = {}
    for row in filtered:
        grouped.setdefault(row['type'], []).append(row)

    for index in range(3):
        event_key = event_table_keys[index]
        event_labels[index].set_text(event_table_titles[index])
        event_tables[index].rows = grouped.get(event_key, [])


def load_data():
    global all_rows
    data = fetch_events()
    all_rows = []
    for r in data:
        all_rows.append({
            'sensor': r[0],
            'type': r[1],
            'timestamp': str(r[2]),
            'frequency': r[3],
            'amplitude': r[4],
        })
    apply_filters()


with ui.card().classes('w-full max-w-6xl mx-auto p-4 shadow-lg'):
    ui.markdown('## Recent Events').classes('mb-3')

    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]
    with ui.row().classes('items-center gap-3 flex-wrap mb-4'):
        ui.markdown('**Sensor filtering**').classes('text-sm font-semibold whitespace-nowrap')
        sensor_filter = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('flix1')


    sensor_filter.on('update:modelValue', lambda e: apply_filters())

    with ui.row().classes('gap-4 flex-wrap'):
        for index in range(3):
            with ui.card().classes('flex-1 min-w-[320px] p-4'):
                with ui.row().classes('items-center justify-between mb-3'):
                    event_labels.append(ui.label(event_table_titles[index]).classes('text-base font-semibold'))
                    ui.button('', on_click=load_data).props('icon=refresh color=primary round').classes('w-7 h-7 text-xs')
                event_tables.append(ui.table(
                    columns=[
                        {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                        {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'sortable': True},
                        {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                        {'name': 'amplitude', 'label': 'Amplitude', 'field': 'amplitude', 'sortable': True},
                    ],
                    rows=[],
                ).classes('w-full'))


load_data()

ui.run()