import psycopg2
from nicegui import ui
from datetime import datetime
from pathlib import Path
import websockets
import asyncio
import json
from nicegui import app
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

### ENVIRONMENTS VARIABLES  
BROKER_HOST = os.getenv('BROKER_HOST', 'localhost')
BROKER_PORT = int(os.getenv('BROKER_PORT', 5000))

DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))


ui.add_head_html('''
<style>
html, body {
    background-color: #0f172a;
    background-image:
        repeating-linear-gradient(45deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 3px, transparent 1px, transparent 30px),
        repeating-linear-gradient(-45deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 3px, transparent 1px, transparent 30px);
}
</style>
''')
ui.label('Fonchi Dashboard').classes('text-3xl font-bold mt-6 mb-4 text-white')

all_rows = []
event_tables = []
event_labels = []
event_table_keys = ['earthquake', 'conventional_explosion', 'nuclear_like']
event_table_titles = ['earthquake', 'conventional explosion', 'nuclear like']

chart=None
live_data = []   

def get_connection():
    try:
        logger.info(f"Connessione al DB: {DB_HOST}:{DB_PORT} (FonchiDB)")
        conn = psycopg2.connect(
            host=DB_HOST,
            database="FonchiDB",
            user="postgres",
            password="fonchi4ever",
            port=DB_PORT
        )
        logger.info("✓ Connessione al database riuscita")
        return conn
    except Exception as e:
        logger.error(f"✗ Errore connessione DB: {e}")
        raise

def fetch_events():
    try:
        logger.info("Fetching events dal database...")
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT sensor_id, event_type, frequency, startstamp, endstamp
            FROM events
            WHERE event_type IN ('earthquake', 'conventional_explosion', 'nuclear_like')
            ORDER BY startstamp DESC
        """)

        rows = cur.fetchall()
        logger.info(f"✓ Recuperati {len(rows)} eventi dal database")
        
        if rows:
            logger.debug(f"Primo record: {rows[0]}")
            logger.debug(f"Ultimo record: {rows[-1]}")

        conn.close()
        return rows
    except Exception as e:
        logger.error(f"✗ Errore fetching events: {e}")
        return []


def apply_filters():
    logger.info("Applicando filtri...")
    sensor_query = ''
    if sensor_filter.value and sensor_filter.value != 'All sensors':
        sensor_query = sensor_filter.value.lower().strip()
        logger.info(f"Filtro sensore attivo: {sensor_query}")
    else:
        logger.info("Nessun filtro sensore")

    filtered = [
        row for row in all_rows
        if not sensor_query or sensor_query in str(row['sensor']).lower()
    ]
    logger.info(f"✓ Filtrati {len(filtered)} su {len(all_rows)} record")

    grouped = {}
    for row in filtered:
        grouped.setdefault(row['type'], []).append(row)

    logger.info(f"Raggruppamento per tipo:")
    for event_type, items in grouped.items():
        logger.info(f"  - {event_type}: {len(items)} record")

    for index in range(3):
        event_key = event_table_keys[index]
        event_count = len(grouped.get(event_key, []))
        event_labels[index].set_text(event_table_titles[index])
        event_tables[index].rows = grouped.get(event_key, [])
        logger.debug(f"  Tabella '{event_table_titles[index]}' aggiornata con {event_count} righe")


async def listen():
    global live_data
    
    max_retries = 10
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info(f"Tentativo di connessione al broker {retry_count + 1}/{max_retries}")
            async with websockets.connect(f"ws://{BROKER_HOST}:{BROKER_PORT}") as ws:
                logger.info("✓ FRONTEND connesso con BROKER")
                message_count = 0

                async for message in ws:
                    try:
                        data = json.loads(message)
                        message_count += 1
                        
                        # Verifica campi obbligatori
                        required_fields = ['sensor_id', 'value', 'timestamp']
                        if not all(field in data for field in required_fields):
                            logger.warning(f"⚠️ Messaggio incompleto ricevuto: {list(data.keys())}")
                            continue
                        
                        # normalizza formato
                        new_row = {
                            'sensor_id': data['sensor_id'],
                            'sensor_value': data['value'],
                            'timestamp': datetime.fromisoformat(data['timestamp'])
                        }

                        live_data.insert(0, new_row)
                        
                        if message_count % 50 == 0:
                            logger.info(f"✓ Ricevuti {message_count} messaggi dal broker, live_data size: {len(live_data)}")
                            logger.info(f"Ricevute le repliche attive dal broker {data['active_replicas']}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"✗ Errore parsing JSON: {e}")
                    except Exception as e:
                        logger.error(f"✗ Errore elaborazione messaggio: {e}")
        
        except Exception as e:
            retry_count += 1
            logger.error(f"✗ Errore connessione broker: {e}, tentativo {retry_count}/{max_retries}")
            if retry_count < max_retries:
                logger.info(f"Attesa 2 secondi prima di ritentare...")
                await asyncio.sleep(2)  # Attendi 2 secondi prima di retry
            else:
                logger.error("✗ Impossibile connettersi al broker dopo 10 tentativi")


def open_realtime_measurements():
    all_measurements = live_data
    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]

    def get_realtime_rows():
        rows = live_data
        if realtime_sensor_select.value != 'All sensors':
            rows = [r for r in rows if r['sensor_id'] == realtime_sensor_select.value]
        return rows

    chart = None
    #chart_data = []

    def open_chart_dialog():
        with ui.dialog() as chart_dialog:
            with ui.card().classes('w-screen h-screen max-w-full max-h-full p-6 bg-slate-900'):

                 ### to save the chart

                async def export_png():
                    # Use NiceGUI's built-in method to call ECharts functions directly
                    url = await chart.run_chart_method(
                        'getDataURL', {
                            'type': 'png',
                            'pixelRatio': 2,
                            'backgroundColor': '#0f172a'
                        }
                    )
                    
                    if url:
                        ui.download(url, filename="sensor_chart.png")
                    else:
                        ui.notify("Could not generate image", type='negative')

                # HEADER
                with ui.row().classes('items-center justify-between w-full mb-6'):
                    ui.label(f'Realtime Sensor: {realtime_sensor_select.value}')\
                        .classes('text-3xl font-bold text-white')
                    ui.button('Export PNG', on_click=export_png).props('icon=image flat dense').classes('text-blue-300 hover:text-blue-200')
                    ui.space()
                    ui.button(on_click=chart_dialog.close)\
                        .props('icon=close flat round dense').classes('text-gray-400 hover:text-red-400')

                # CARD GRAFICO
                with ui.card().classes('w-full h-full bg-slate-800 shadow-2xl rounded-2xl p-4'):
                    global  chart
                    
                    chart = ui.echart({
                        'backgroundColor': 'transparent',

                        'tooltip': {
                            'trigger': 'axis'
                        },

                        'xAxis': {
                            'type': 'category',
                            'data': [],
                            'axisLabel': {'color': '#cbd5f5'}
                        },

                        'yAxis': {
                            'type': 'value',
                            'axisLabel': {'color': '#cbd5f5'}
                        },

                        'series': [{
                            'data': [],
                            'type': 'line',
                            'smooth': True,
                            'lineStyle': {
                                'width': 3
                            },
                            'areaStyle': {}  
                        }]
                    }).classes('w-full h-[80vh]')

                    def update_chart():
                        rows = get_realtime_rows()

                        if realtime_sensor_select.value != 'All sensors':

                            last_points = rows[:500][::-1]   

                            x = [r['timestamp'].strftime('%H:%M:%S') for r in last_points]
                            y = [r['sensor_value'] for r in last_points]

                            chart.options['xAxis']['data'] = x
                            chart.options['series'][0]['data'] = y

                            chart.update()

                    ui.timer(1.0, update_chart)

        chart_dialog.open()

    with ui.dialog() as dialog:
        with ui.card().classes('w-screen h-screen max-w-full max-h-full p-4'):
            with ui.row().classes('items-center justify-between w-full mb-4'):
                ui.markdown('## REAL TIME Measurements').classes('text-2xl font-bold text-black m-0')
                ui.space()
                ui.button(on_click=dialog.close).props('icon=close flat round dense').classes('text-gray-400 hover:text-red-400')
            with ui.row().classes('items-center gap-4 mb-4'):
                realtime_sensor_select = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('w-56')
                show_chart_button = ui.button('SHOW CHART', on_click=open_chart_dialog).props('flat no-caps').classes('rounded-lg px-4 py-2 bg-gray-800 text-white')

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
    logger.info("Loading data dal database...")
    data = fetch_events()
    all_rows = []
    
    for r in data:
        all_rows.append({
            'sensor': r[0],
            'type': r[1],
            'frequency': r[2],
            'startstamp': str(r[3]),
            'endstamp': str(r[4]),
        })
    
    logger.info(f"✓ Caricati {len(all_rows)} record in all_rows")
    
    # Verifica il contenuto
    if all_rows:
        logger.debug(f"Primo record: {all_rows[0]}")
        types_count = {}
        for row in all_rows:
            event_type = row['type']
            types_count[event_type] = types_count.get(event_type, 0) + 1
        logger.info(f"Distribuzione tipi evento: {types_count}")
    
    apply_filters()


with ui.card().classes('w-full max-w-6xl mx-auto p-4 shadow-lg'):
    with ui.row().classes('items-center mb-3 gap-4'):
        ui.markdown('## Recent Events').classes('mb-0')
        ui.button('PRESS TO WATCH REAL TIME MEASUREMENTS', on_click=open_realtime_measurements).props('flat no-caps').classes('rounded-3xl px-30 py-10 bg-slate-900 text-white text-xl font-semibold shadow-xl hover:bg-slate-700 hover:shadow-blue-500/30 transition-all duration-300 ml-35')

    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]
    with ui.row().classes('items-center gap-3 flex-wrap mb-4'):
        ui.markdown('**Sensor filtering**').classes('text-sm font-semibold whitespace-nowrap')
        sensor_filter = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('flix1')


    sensor_filter.on('update:modelValue', lambda e: apply_filters())

    with ui.row().classes('gap-4 w-full flex-nowrap'):
        for index in range(3):
            with ui.card().classes('flex-1 min-w-0 p-2'):
                with ui.row().classes('items-center justify-between w-full mb-2'):
                    event_labels.append(ui.label(event_table_titles[index]).classes('text-sm font-semibold'))
                    ui.space()
                    ui.button('', on_click=load_data).props('icon=refresh flat round dense size=sm').classes('w-4 h-4 text-xs')
                
                table = ui.table(
                    columns=[
                        {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                        {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                        {'name': 'startstamp', 'label': 'Startstamp', 'field': 'startstamp', 'sortable': True},
                        {'name': 'endstamp', 'label': 'Endstamp', 'field': 'endstamp', 'sortable': True}
                    ],
                    rows=[],
                ).classes('w-full cursor-pointer hover:opacity-75 transition-opacity')
                event_tables.append(table)
                
                def open_fullscreen_table(idx=index):
                    with ui.dialog() as dialog:
                        with ui.card().classes('w-full max-w-6xl p-4'):
                            with ui.row().classes('items-center justify-between w-full mb-4'):
                                ui.label(event_table_titles[idx]).classes('text-2xl font-bold text-black')

                                with ui.row().classes('items-center gap-2'):
                                    ui.button(on_click=load_data)\
                                        .props('icon=refresh flat round dense size=sm')\
                                        .classes('text-gray-400 hover:text-blue-400')

                                    ui.button(on_click=dialog.close)\
                                        .props('icon=close flat round dense size=sm')\
                                        .classes('text-gray-400 hover:text-red-400')
                            ui.table(
                                columns=[
                                    {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                                    {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                                    {'name': 'startstamp', 'label': 'Startstamp', 'field': 'startstamp', 'sortable': True},
                                    {'name': 'endstamp', 'label': 'Endstamp', 'field': 'endstamp', 'sortable': True}
                                ],
                                rows=event_tables[idx].rows,
                            ).classes('w-full')
                    
                    dialog.open()
                
                table.on('click', open_fullscreen_table)


load_data()

# AUTO-REFRESH: Aggiorna le tabelle di evento ogni 5 secondi dal database
def refresh_events():
    logger.debug("🔄 Refresh automatico eventi dal database...")
    load_data()

ui.timer(5.0, refresh_events, once=False)
logger.info("✓ Auto-refresh tabelle evento abilitato (ogni 5 secondi)")

logger.info("="*60)
logger.info("🚀 Fonchi Dashboard UI Inizializzato")
logger.info(f"   DB: {DB_HOST}:{DB_PORT} (FonchiDB)")
logger.info(f"   Broker: {BROKER_HOST}:{BROKER_PORT} (WebSocket)")
logger.info(f"   Dashboard: http://localhost:5030")
logger.info("="*60)

# Avvia il listener in background con NiceGUI timer
async def start_listening():
    await listen()

ui.timer(0.1, lambda: asyncio.create_task(start_listening()), once=True)

ui.run()