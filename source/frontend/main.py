"""
Fonchi Dashboard - Monitoraggio sismico distribuito in tempo reale
Applicazione NiceGUI per visualizzare eventos e misurazioni real-time dal broker
"""

import psycopg2
from nicegui import ui
from datetime import datetime
from pathlib import Path
import websockets
import asyncio
import json
import os
import logging
import base64
from nicegui import context

# ===================== SETUP LOGGING =====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== CONFIGURATION =====================
BROKER_HOST = os.getenv('BROKER_HOST', 'localhost')
BROKER_PORT = int(os.getenv('BROKER_PORT', 5000))
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = "FonchiDB"
DB_USER = "postgres"
DB_PASSWORD = "fonchi4ever"

# ===================== CONSTANTS =====================
# IMPORTANTE: Questi DEVONO corrispondere alle chiavi nel database!
EVENT_TYPES = {
    'earthquake': 'Earthquake',
    'conventional_explosion': 'Conventional Explosion',  
    'nuclear_like': 'Nuclear-like'  
}

REFRESH_INTERVAL = 5.0  # Secondi
WEBSOCKET_RETRY_MAX = 10
WEBSOCKET_RETRY_DELAY = 2
MAX_LIVE_DATA_POINTS = 500  # Max punti da keepare in memoria
MAX_CHART_POINTS = 500  # Punti da mostrare nel chart (smart decimation per performance)


# ===================== UI THEME =====================
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

# ===================== GLOBAL STATE =====================
all_rows = []
event_tables = {}
event_labels = {}
live_data = []
chart = None


# ===================== DATABASE FUNCTIONS =====================
def get_connection():
    """Crea una connessione al database"""
    try:
        logger.info(f"Connecting to DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        logger.info("✓ Database connection successful")
        return conn
    except Exception as e:
        logger.error(f"✗ Database connection error: {e}")
        raise


def fetch_events():
    """Recupera tutti gli eventi dal database"""
    try:
        logger.info("Fetching events from database...")
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT sensor_id, event_type, frequency, startstamp, endstamp 
            FROM events
            ORDER BY startstamp DESC
        """)

        rows = cur.fetchall()
        logger.info(f"✓ Retrieved {len(rows)} events from database")
        
        if rows:
            logger.debug(f"First record: {rows[0]}")
            logger.debug(f"Last record: {rows[-1]}")

        conn.close()
        return rows
    except Exception as e:
        logger.error(f"✗ Error fetching events: {e}")
        return []


def get_event_statistics():
    """Calcola statistiche sugli eventi"""
    events = fetch_events()
    stats = {}
    for event in events:
        event_type = event[1]  # event_type è il secondo campo
        stats[event_type] = stats.get(event_type, 0) + 1
    return stats


# ===================== FILTERING FUNCTIONS =====================
def apply_filters():
    """Filtra gli eventi e aggiorna le tabelle"""
    global all_rows, event_tables, event_labels
    
    logger.info("Applying filters...")
    
    # Get sensor filter
    sensor_query = ''
    if sensor_filter.value and sensor_filter.value != 'All sensors':
        sensor_query = sensor_filter.value.lower().strip()
        logger.info(f"Sensor filter active: {sensor_query}")
    
    # Filter events by sensor
    filtered = [
        row for row in all_rows
        if not sensor_query or sensor_query in str(row['sensor']).lower()
    ]
    logger.info(f"✓ Filtered {len(filtered)} out of {len(all_rows)} events")
    
    # Group by event type
    grouped = {}
    for row in filtered:
        event_type = row['type']
        if event_type not in grouped:
            grouped[event_type] = []
        grouped[event_type].append(row)
    
    logger.info("Event distribution:")
    for event_type, items in grouped.items():
        logger.info(f"  - {event_type}: {len(items)} events")
    
    # Update each table
    for event_type, table in event_tables.items():
        events = grouped.get(event_type, [])
        table.rows = events
        logger.debug(f"Updated '{event_type}' table with {len(events)} rows")


# ===================== DATA LOADING =====================
def load_data():
    """Carica i dati dal database e aggiorna le tabelle"""
    global all_rows
    
    logger.info("Loading data from database...")
    data = fetch_events()
    all_rows = []
    
    # Convert database rows to display format
    for r in data:
        all_rows.append({
            'sensor': r[0],
            'type': r[1],
            'frequency': f"{float(r[2]):.2f} Hz",
            'startstamp': str(r[3]),
            'endstamp': str(r[4]),
        })
    
    logger.info(f"✓ Loaded {len(all_rows)} events")
    
    # Show statistics
    stats = get_event_statistics()
    for event_type, count in stats.items():
        logger.info(f"  - {event_type}: {count} events")
    
    # Apply filters and update tables
    apply_filters()


# ===================== WEBSOCKET BROKER =====================
async def listen():
    """Rimane in ascolto dal broker WebSocket"""
    global live_data
    
    retry_count = 0

    while retry_count < WEBSOCKET_RETRY_MAX:
        try:
            logger.info(f"WebSocket connection attempt {retry_count + 1}/{WEBSOCKET_RETRY_MAX}")
            async with websockets.connect(f"ws://{BROKER_HOST}:{BROKER_PORT}") as ws:
                logger.info("✓ FRONTEND connected to BROKER")
                message_count = 0

                async for message in ws:
                    try:
                        data = json.loads(message)
                        message_count += 1
                        
                        # Validate required fields
                        required_fields = ['sensor_id', 'value', 'timestamp']
                        if not all(field in data for field in required_fields):
                            logger.warning(f"⚠️ Incomplete message: {list(data.keys())}")
                            continue
                        
                        # Create measurement object
                        new_row = {
                            'sensor_id': data['sensor_id'],
                            'sensor_value': f"{float(data['value']):.4f}",
                            'timestamp': datetime.fromisoformat(data['timestamp'])
                        }

                        live_data.insert(0, new_row)
                        if len(live_data) > MAX_LIVE_DATA_POINTS:
                            live_data = live_data[:MAX_LIVE_DATA_POINTS]
                        
                        if message_count % 50 == 0:
                            logger.info(f"✓ Received {message_count} messages from broker, live_data size: {len(live_data)}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"✗ JSON parsing error: {e}")
                    except Exception as e:
                        logger.error(f"✗ Message processing error: {e}")
        
        except Exception as e:
            retry_count += 1
            logger.error(f"✗ Broker connection error: {e}, attempt {retry_count}/{WEBSOCKET_RETRY_MAX}")
            if retry_count < WEBSOCKET_RETRY_MAX:
                logger.info(f"Retrying in {WEBSOCKET_RETRY_DELAY} seconds...")
                await asyncio.sleep(WEBSOCKET_RETRY_DELAY)
            else:
                logger.error("✗ Failed to connect to broker after max retries")




# ===================== REAL-TIME VIEWER =====================
async def export_png(chart_obj):
    """Esporta il grafico come PNG - Download dal browser"""
    try:
        logger.info("Exporting PNG...")
        
        # Recupera l'immagine dal chart
        data_url = await chart_obj.run_chart_method('getDataURL', {'type': 'png'})
        
        # Estrai il base64
        img_base64 = data_url.split(',')[1] if ',' in data_url else data_url
        
        # Converti a bytes
        img_bytes = base64.b64decode(img_base64)
        
        # Download nel browser
        filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        ui.download(img_bytes, filename)
        
        logger.info(f"✓ PNG download: {filename}")
        
    except Exception as e:
        logger.error(f"✗ Export error: {e}", exc_info=True)


def open_realtime_measurements():
    """Apre la finestra delle misurazioni real-time"""
    global chart
    
    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]

    def get_realtime_rows():
        rows = live_data
        if realtime_sensor_select.value != 'All sensors':
            rows = [r for r in rows if r['sensor_id'] == realtime_sensor_select.value]
        return rows

    def open_chart_dialog():
        with ui.dialog() as chart_dialog:
            with ui.card().classes('w-screen h-screen max-w-full max-h-full p-6 bg-slate-900'):
                # Header
                with ui.row().classes('items-center justify-between w-full mb-6'):
                    ui.label(f'Realtime Sensor: {realtime_sensor_select.value}')\
                        .classes('text-3xl font-bold text-white')
                    with ui.row().classes('gap-2'):
                        export_btn_placeholder = ui.button('Export PNG').props('icon=image flat dense')\
                            .classes('text-blue-300 hover:text-blue-200')
                        ui.button(on_click=chart_dialog.close)\
                            .props('icon=close flat round dense').classes('text-gray-400 hover:text-red-400')

                # Chart card
                with ui.card().classes('w-full h-full bg-slate-800 shadow-2xl rounded-2xl p-4'):
                    chart = ui.echart({
                        'backgroundColor': 'transparent',
                        'tooltip': {'trigger': 'axis'},
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
                            'lineStyle': {'width': 3},
                            'areaStyle': {}
                        }]
                    }).classes('w-full h-[80vh]')

                    # Collega il bottone export al chart
                    export_btn_placeholder.on_click(lambda: asyncio.create_task(export_png(chart)))

                    def update_chart():
                        rows = get_realtime_rows()
                        if realtime_sensor_select.value != 'All sensors' and rows:
                            # Take last MAX_CHART_POINTS data points and reverse for correct order (old → new)
                            last_points = rows[:MAX_CHART_POINTS][::-1]
                            
                            # Smart decimation: if too many points, show every Nth to reduce render load
                            if len(last_points) > 150:
                                display_points = last_points[::2]
                                logger.debug(f"Chart decimated: {len(last_points)} → {len(display_points)} points")
                            else:
                                display_points = last_points
                            
                            x = [r['timestamp'].strftime('%H:%M:%S') for r in display_points]
                            y = [float(r['sensor_value']) for r in display_points]
                            chart.options['xAxis']['data'] = x
                            chart.options['series'][0]['data'] = y
                            chart.update()
                            logger.debug(f"Chart updated with {len(display_points)} points for {realtime_sensor_select.value}")

                    ui.timer(1.0, update_chart)

        chart_dialog.open()

    with ui.dialog() as dialog:
        with ui.card().classes('w-screen h-screen max-w-full max-h-full p-4'):
            # Header
            with ui.row().classes('items-center justify-between w-full mb-4'):
                ui.markdown('## REAL TIME Measurements').classes('text-2xl font-bold text-black m-0')
                ui.button(on_click=dialog.close).props('icon=close flat round dense')\
                    .classes('text-gray-400 hover:text-red-400')
            
            # Controls
            with ui.row().classes('items-center gap-4 mb-4'):
                realtime_sensor_select = ui.select(sensor_options, label='Filter sensor',
                                                   value='All sensors').classes('w-56')
                show_chart_button = ui.button('SHOW CHART', on_click=open_chart_dialog)\
                    .props('flat no-caps').classes('rounded-lg px-4 py-2 bg-gray-800 text-white')

            # Table
            realtime_table = ui.table(
                columns=[
                        {'name': 'sensor_id', 'label': 'Sensor', 'field': 'sensor_id', 'sortable': True},
                        {'name': 'sensor_value', 'label': 'Value', 'field': 'sensor_value', 'sortable': True},
                        {'name': 'timestamp', 'label': 'Timestamp', 'field': 'timestamp', 'sortable': True},
                    ],
                rows=live_data,
            ).classes('w-full h-full')

            def update_filter(e):
                show_chart_button.visible = realtime_sensor_select.value != 'All sensors'
                realtime_table.rows = get_realtime_rows()

            def refresh_realtime():
                rows = get_realtime_rows()
                realtime_table.rows = rows

            realtime_sensor_select.on('update:modelValue', update_filter)
            ui.timer(1.0, refresh_realtime, once=False)
            update_filter(None)

    dialog.open()


# ===================== UI LAYOUT =====================
with ui.card().classes('w-full max-w-6xl mx-auto p-4 shadow-lg'):
    # Header
    with ui.row().classes('items-center mb-3 gap-4'):
        ui.markdown('## Recent Events').classes('mb-0')
        ui.button('PRESS TO WATCH REAL TIME MEASUREMENTS', on_click=open_realtime_measurements)\
            .props('flat no-caps').classes('rounded-3xl px-30 py-10 bg-slate-900 text-white text-xl font-semibold shadow-xl hover:bg-slate-700 hover:shadow-blue-500/30 transition-all duration-300 ml-35')

    # Sensor filter
    sensor_options = ['All sensors'] + [f'sensor-{i:02d}' for i in range(1, 13)]
    sensor_filter = ui.select(sensor_options, label='Filter sensor', value='All sensors').classes('w-56')
    
    with ui.row().classes('items-center gap-3 flex-wrap mb-4'):
        ui.markdown('**Sensor filtering**').classes('text-sm font-semibold whitespace-nowrap')
        sensor_filter

    sensor_filter.on('update:modelValue', lambda e: apply_filters())

    # Three event type tables
    with ui.row().classes('gap-4 w-full flex-nowrap'):
        for event_type, event_label in EVENT_TYPES.items():
            with ui.card().classes('flex-1 min-w-0 p-2'):
                # Card header
                with ui.row().classes('items-center justify-between w-full mb-2'):
                    label = ui.label(event_label).classes('text-sm font-semibold')
                    ui.space()
                    ui.button('', on_click=load_data).props('icon=refresh flat round dense size=sm')\
                        .classes('w-4 h-4 text-xs')
                
                # Table
                table = ui.table(
                    columns=[
                        {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                        {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                        {'name': 'startstamp', 'label': 'Startstamp', 'field': 'startstamp', 'sortable': True},
                        {'name': 'endstamp', 'label': 'Endstamp', 'field': 'endstamp', 'sortable': True},
                    ],
                    rows=[],
                ).classes('w-full cursor-pointer hover:opacity-75 transition-opacity')
                
                event_tables[event_type] = table
                event_labels[event_type] = label
                
                # Make table clickable for fullscreen view
                def on_table_click(etype=event_type, elabel=event_label):
                    with ui.dialog() as dialog:
                        with ui.card().classes('w-full max-w-6xl p-4'):
                            with ui.row().classes('items-center justify-between w-full mb-4'):
                                ui.label(elabel).classes('text-2xl font-bold text-black')
                                with ui.row().classes('items-center gap-2'):
                                    ui.button(on_click=load_data).props('icon=refresh flat round dense size=sm')\
                                        .classes('text-gray-400 hover:text-blue-400')
                                    ui.button(on_click=dialog.close).props('icon=close flat round dense size=sm')\
                                        .classes('text-gray-400 hover:text-red-400')
                            
                            ui.table(
                                columns=[
                                    {'name': 'sensor', 'label': 'Sensor', 'field': 'sensor', 'sortable': True},
                                    {'name': 'frequency', 'label': 'Frequency', 'field': 'frequency', 'sortable': True},
                                    {'name': 'startstamp', 'label': 'Startstamp', 'field': 'startstamp', 'sortable': True},
                                    {'name': 'endstamp', 'label': 'Endstamp', 'field': 'endstamp', 'sortable': True},
                                ],
                                rows=event_tables[etype].rows,
                            ).classes('w-full')
                    
                    dialog.open()
                
                table.on('click', on_table_click)


# ===================== INITIALIZATION =====================
def init_dashboard():
    """Inizializza il dashboard"""
    logger.info("Initializing Fonchi Dashboard...")
    
    # Load initial data
    load_data()
    
    # Setup auto-refresh timer
    ui.timer(REFRESH_INTERVAL, load_data, once=False)
    logger.info(f"✓ Auto-refresh enabled (every {REFRESH_INTERVAL} seconds)")
    
    # Start broker listener in background
    async def start_listener():
        await listen()
    
    ui.timer(0.1, lambda: asyncio.create_task(start_listener()), once=True)
    
    # Log startup info
    logger.info("=" * 60)
    logger.info("🚀 Fonchi Dashboard Initialized")
    logger.info(f"   DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    logger.info(f"   Broker: {BROKER_HOST}:{BROKER_PORT} (WebSocket)")
    logger.info(f"   Dashboard: http://localhost:5030")
    logger.info("=" * 60)


# Initialize on app start
init_dashboard()


ui.run()