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
        SELECT sensor_id, event_type, timestamp, frequency 
        FROM events
        ORDER BY timestamp DESC
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


def fetch_measurements():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT sensor_id, sensor_value, timestamp FROM measurements ORDER BY timestamp DESC;')
    rows = cur.fetchall()
    conn.close()
    return [
        {'sensor_id': r[0], 'sensor_value': r[1], 'timestamp': r[2]} for r in rows
    ]


def open_realtime_measurements():
    all_measurements = fetch_measurements()
    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]

    def get_realtime_rows():
        rows = fetch_measurements()
        if realtime_sensor_select.value and realtime_sensor_select.value != 'All sensors':
            rows = [r for r in rows if r['sensor_id'] == realtime_sensor_select.value]
        return rows

    chart = None
    #chart_data = []

    def open_chart_dialog():
        with ui.dialog() as chart_dialog:
            with ui.card().classes('w-screen h-screen max-w-full max-h-full p-4'):
                
                # HEADER
                with ui.row().classes('items-center justify-between mb-4'):
                    ui.label('Realtime Chart').classes('text-2xl font-bold text-white')
                    ui.button('Close', on_click=chart_dialog.close).props('icon=close color=negative')

                # GRAFICO
                chart = ui.echart({
                    'xAxis': {'type': 'category', 'data': []},
                    'yAxis': {'type': 'value'},
                    'series': [{
                        'data': [],
                        'type': 'line',
                        'smooth': True
                    }]
                }).classes('w-full h-full')

                # UPDATE REALTIME
                def update_chart():
                    rows = get_realtime_rows()

                    if realtime_sensor_select.value != 'All sensors':
                        last_points = rows[:50][::-1]

                        x = [r['timestamp'].strftime('%H:%M:%S') for r in last_points]
                        y = [r['sensor_value'] for r in last_points]

                        chart.options['xAxis']['data'] = x
                        chart.options['series'][0]['data'] = y

                        chart.update()

                ui.timer(1.0, update_chart)

        chart_dialog.open()

    with ui.dialog() as dialog:
        with ui.card().classes('w-screen h-screen max-w-full max-h-full p-4'):
            with ui.row().classes('items-center justify-between mb-4'):
                ui.markdown('## REAL TIME Measurements').classes('text-2xl font-bold text-white m-0')
                ui.button('Close', on_click=dialog.close).props('icon=close color=negative')
            with ui.row().classes('items-center gap-4 mb-4'):
                realtime_sensor_select = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('w-56')
                show_chart_button = ui.button('Mostra grafico', on_click=open_chart_dialog).classes('rounded-lg px-4 py-2 bg-gray-600 text-white')

            realtime_table = ui.table(
                columns=[
                    {'name': 'sensor_id', 'label': 'Sensor', 'field': 'sensor_id', 'sortable': True},
                    {'name': 'sensor_value', 'label': 'Value', 'field': 'sensor_value', 'sortable': True},
                    {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'sortable': True}
                ],
                rows=all_measurements,
            ).classes('w-full h-full')

    def update_filter(e):
        show_chart_button.visible = realtime_sensor_select.value != 'All sensors'
        realtime_table.rows = get_realtime_rows()

    realtime_sensor_select.on('update:modelValue', update_filter)
    update_filter(None)


    def refresh_realtime():
        rows = get_realtime_rows()
        realtime_table.rows = rows

        if chart and realtime_sensor_select.value != 'All sensors':
            # prendi solo ultimi N punti
            last_points = rows[:50][::-1]  # ordine corretto

            x = [r['timestamp'][-8:] for r in last_points]
            y = [r['sensor_value'] for r in last_points]

            chart.options['xAxis']['data'] = x
            chart.options['series'][0]['data'] = y

            chart.update()

    ui.timer(1.0, refresh_realtime, once=False)
    dialog.open()


def load_data():
    global all_rows
    data = fetch_events()
    all_rows = []
    for r in data:
        all_rows.append({
            'sensor': r[0],
            'type': r[1],
            'timestamp': str(r[2]),
            'frequency': r[3]
        })
    apply_filters()


with ui.card().classes('w-full max-w-6xl mx-auto p-4 shadow-lg'):
    with ui.row().classes('items-center mb-3 gap-4'):
        ui.markdown('## Recent Events').classes('mb-0')
        ui.button('REAL TIME', on_click=open_realtime_measurements).classes('rounded-lg px-30 py-10 bg-blue-600 text-3xl ml-55')

    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]
    with ui.row().classes('items-center gap-3 flex-wrap mb-4'):
        ui.markdown('**Sensor filtering**').classes('text-sm font-semibold whitespace-nowrap')
        sensor_filter = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('flix1')


    sensor_filter.on('update:modelValue', lambda e: apply_filters())

    with ui.row().classes('gap-4 w-full flex-nowrap'):
        for index in range(3):
            with ui.card().classes('flex-1 min-w-0 p-2'):
                with ui.row().classes('items-center justify-between mb-2'):
                    event_labels.append(ui.label(event_table_titles[index]).classes('text-sm font-semibold'))
                    ui.button('', on_click=load_data).props('icon=refresh color=primary round').classes('w-6 h-6 text-xs')
                
                table = ui.table(
                    columns=[
                        {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                        {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                        {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'sortable': True}
                    ],
                    rows=[],
                ).classes('w-full cursor-pointer hover:opacity-75 transition-opacity')
                event_tables.append(table)
                
                def open_fullscreen_table(idx=index):
                    with ui.dialog() as dialog:
                        with ui.card().classes('w-full max-w-6xl p-4'):
                            with ui.row().classes('items-center justify-between mb-4'):
                                ui.label(event_table_titles[idx]).classes('text-2xl font-bold text-white')
                                ui.button('Close', on_click=dialog.close).props('icon=close color=negative')
                            
                            ui.table(
                                columns=[
                                    {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                                    {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                                    {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'sortable': True}
                                ],
                                rows=event_tables[idx].rows,
                            ).classes('w-full')
                    
                    dialog.open()
                
                table.on('click', open_fullscreen_table)


load_data()

ui.run()