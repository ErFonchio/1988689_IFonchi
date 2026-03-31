# FONCHI - Distributed Seismic Monitoring System

## SYSTEM DESCRIPTION:

Fonchi is a distributed real-time seismic signal processing and monitoring system designed to detect and classify seismic events. The system uses a Master-Broker-Slave architecture with frequency analysis to classify events as earthquakes, conventional explosions, nuclear-like events, or base noise. Multiple sensor replicas process signals in parallel, with a centralized broker collecting data and a PostgreSQL database storing analysis results. A real-time NiceGUI frontend displays events, measurements, and replica status through WebSocket streaming.

## USER STORIES:

1.  As a Client I want to see the events on a dasboard
2.  As a Client, I want to know wich are the main events
3.  As a Client, for each event, I want to see a dedicated widget
4.  As a Client, in each event widget, I want to see, the sensor, frequency, startstamp, endstamp
5.  As a Client, I want to be able to refresh the event widget 
6.  As a Client, I want to be able to inspect the single event widget.
7.  As a Client, I want to inspect the historical events
8.  As a Client, I want to see in real time the data transmitted by the sensors
9.  As a Client, I want to see a sliding window of the plotted data.
10. As a Client, I want to be able to filter the real time data based on the sensor
11. As a Client, I want be able to plot the sensor's transmitted data 
12. As a Client, I want to see the evolution of the plot in time
13. As a Client, I want to be able to hover on the points of the plot and inspect the single value.
14. As a Client, I want to be able to export the plot in png format
15. As a Client, I want to inspect the historical events on the dashboard
16. As a Client, I want to be notified when the site goes down
17. As an Admin, I want to be able to login
18. As an Admin, I want to be able to logout
19. As an Admin, I want to be able to see the number of replicas
20. As an Admin, I want to see which replicas are alive or not


## CONTAINERS:

## CONTAINER_NAME: Broker

### DESCRIPTION:
Manages WebSocket connections, coordinates Master-Broker-Slave communication, handles real-time data streaming, and maintains socket-based synchronization with replicas.

### USER STORIES:
8.  As a Client, I want to see in real time the data transmitted by the sensors
10. As a Client, I want to be able to filter the real time data based on the sensor
13. As a Client, I want to be able to hover on the points of the plot and inspect the single value
16. As a Client, I want to be notified when the site goes down

### PORTS:
5000 (WebSocket), 5001 (TCP Socket)

### DESCRIPTION:
The Broker container acts as the central hub for the distributed seismic monitoring system. It maintains WebSocket connections with the frontend for real-time data streaming, manages socket-based communication with multiple replicas, implements Master-Broker-Slave architecture with ACK protocol and leader election, and forwards real-time sensor measurements to connected clients.

### PERSISTENCE EVALUATION:
The Broker container does not require persistent storage; all data is streamed in real-time and delegated to the database for persistence.

### EXTERNAL SERVICES CONNECTIONS:
The Broker connects to the PostgreSQL database for event storage and to multiple Replica instances for signal processing tasks.

### MICROSERVICES:

#### MICROSERVICE: broker
- TYPE: backend
- DESCRIPTION: Manages WebSocket connections with the frontend, coordinates Master-Broker-Slave architecture with replica coordination via TCP sockets, implements ACK protocol and leader election, forwards real-time measurements to frontend clients.
- PORTS: 5000 (WebSocket), 5001 (TCP)
- TECHNOLOGICAL SPECIFICATION:

  - Python 3.11
  - asyncio for asynchronous event handling
  - websockets library for WebSocket server
  - socket library for TCP communication with replicas
  - psycopg2 for PostgreSQL integration
  - Master-Slave coordination protocol with heartbeat and ACK mechanism
  - Leader election algorithm for replica management

- SERVICE ARCHITECTURE:
  - WebSocket server handling multiple client connections
  - TCP socket manager for replica communication
  - Master-Broker state machine managing replica states
  - Real-time data relay forwarding sensor measurements to frontend
  - Event aggregation from multiple replicas
---

## CONTAINER_NAME: Replica

### DESCRIPTION:
Processes seismic signals using FFT frequency analysis, classifies events, communicates with broker via TCP socket, and stores results in PostgreSQL database.

### USER STORIES:
8.  As a Client, I want to see in real time the data transmitted by the sensors
11. As a Client, I want be able to plot the sensor's transmitted data 
19. As an Admin, I want to be able to see the number of replicas
20. As an Admin, I want to see which replicas are alive or not

### PORTS:
Multiple instances (5 replicas total)

### DESCRIPTION:
Each Replica container is responsible for processing raw seismic signals from 12 sensor channels using FFT frequency analysis. It classifies detected events based on dominant frequency bands into event categories (earthquake, conventional_explosion, nuclear_like, base). Communication with the broker is handled via TCP socket with ACK protocol. All analyzed events are stored in the PostgreSQL database with timestamp and frequency information.


### PERSISTENCE EVALUATION:
Replica containers require access to the PostgreSQL database to persist event analysis results (sensor_id, event_type, startstamp, endstamp, frequency).

### EXTERNAL SERVICES CONNECTIONS:
Each Replica connects to the Broker (TCP socket) for coordination and to PostgreSQL for event storage.

### MICROSERVICES:

#### MICROSERVICE: replica
- TYPE: backend (signal processing)
- DESCRIPTION: Processes 12 parallel sensor channels using FFT analysis, classifies events based on dominant frequency, sends classification results to broker via TCP socket, stores events in PostgreSQL database.
- PORTS: Ephemeral (TCP communication with broker)
- TECHNOLOGICAL SPECIFICATION:
  - Python 3.11
  - numpy and scipy for FFT frequency analysis
  - Signal generation and processing (simulating 12 sensor channels)
  - psycopg2 for PostgreSQL database operations
  - TCP socket communication with ACK protocol
  - Event classification algorithm based on frequency bands

- SERVICE ARCHITECTURE:
  - Signal simulator generating 12 parallel sensor streams
  - FFT analyzer computing dominant frequency per sensor
  - Event classifier determining event_type based on frequency ranges
  - TCP socket client for broker communication
  - Database persistence layer for event storage

- FREQUENCY CLASSIFICATION BANDS:
  - Base/Noise: < 0.5 Hz
  - Earthquake: 0.5-3.0 Hz
  - Conventional Explosion: 3.0-8.0 Hz
  - Nuclear-like: > 8.0 Hz

---

## CONTAINER_NAME: Database

### DESCRIPTION:
Persistent storage for all analyzed seismic events, providing historical data for analysis and reporting.

### USER STORIES:
1.  As a Client I want to see the events on a dasboard
5.  As a Client, I want to be able to refresh the event widget
7. As a Client, I want to inspect the historical events

### PORTS:
5432 (PostgreSQL)

### DESCRIPTION:
The Database container maintains persistent storage of all seismic event analysis results. It provides efficient query capabilities for retrieving events by sensor, event type, date range, or other criteria. The database schema supports the storage of frequency analysis results and timestamps for comprehensive event documentation.

### PERSISTENCE EVALUATION:
The Database container provides the primary data persistence for the entire system, storing all event analysis results in PostgreSQL.

### EXTERNAL SERVICES CONNECTIONS:
The Database connects to Replica instances for event storage and to the Frontend/Broker for event retrieval and real-time updates.

### MICROSERVICES:

#### MICROSERVICE: postgresql
- TYPE: database
- DESCRIPTION: Manages persistent storage of all seismic event analysis results with indexed queries for efficient retrieval.
- PORTS: 5432
- DATABASE TABLES:

  **_events_** table:
  | Column | Type | Description |
  | --- | --- | --- |
  | sensor_id | TEXT | Identifier of the sensor (e.g., sensor-01 to sensor-12) |
  | event_type | TEXT | Classification: 'earthquake', 'conventional_explosion', 'nuclear_like', 'base' |
  | startstamp | TIMESTAMPTZ | Event start timestamp |
  | endstamp | TIMESTAMPTZ | Event end timestamp |
  | frequency | DOUBLE PRECISION | Dominant frequency in Hz |
  | PRIMARY KEY | (sensor_id, startstamp, endstamp) | Composite key for uniqueness |

- KEY FEATURES:
  - Auto-initialization on first run
  - Indexed queries on sensor_id and event_type for fast filtering
  - 1400+ events stored and queryable
  - TIMESTAMPTZ support for accurate timestamp handling
  - Automatic vacuum and maintenance

---

## CONTAINER_NAME: Frontend

### DESCRIPTION:
Real-time dashboard for monitoring seismic events, viewing measurements, filtering by sensor, and accessing administrative features.

### USER STORIES:
1.  As a Client I want to see the events on a dasboard
2.  As a Client, I want to know wich are the main events
3.  As a Client, for each event, I want to see a dedicated widget
4.  As a Client, in each event widget, I want to see, the sensor, frequency, startstamp, endstamp 
6.  As a Client, I want to be able to inspect the single event widget.
9.  As a Client, I want to see a sliding window of the plotted data.
10. As a Client, I want to be able to filter the real time data based on the sensor
11. As a Client, I want be able to plot the sensor's transmitted data 
12. As a Client, I want to see the evolution of the plot in time
13. As a Client, I want to be able to hover on the points of the plot and inspect the single value.
14. As a Client, I want to be able to export the plot in png format
15. As a Client, I want to inspect the historical events on the dashboard
17. As an Admin, I want to be able to login
18. As an Admin, I want to be able to logout
19. As an Admin, I want to be able to see the number of replicas

### PORTS:
5030 (NiceGUI)

### DESCRIPTION:
The Frontend container provides a comprehensive real-time monitoring dashboard built with NiceGUI. It displays recent seismic events grouped by event type (Earthquake, Conventional Explosion, Nuclear-like), supports sensor-based filtering, streams live measurements via WebSocket, and provides admin features for replica status monitoring and chart downloading.

### PERSISTENCE EVALUATION:
The Frontend container does not require persistent storage; all data is fetched from the database or streamed from the broker in real-time.

### EXTERNAL SERVICES CONNECTIONS:
The Frontend connects to the Broker (WebSocket) for real-time data streaming and to the Database for historical event retrieval.

### MICROSERVICES:

#### MICROSERVICE: frontend
- TYPE: frontend (dashboard)
- DESCRIPTION: Real-time seismic monitoring dashboard with event display, sensor filtering, live charts, and admin panel.
- PORTS: 5030
- TECHNOLOGICAL SPECIFICATION:
  - Python 3.11
  - NiceGUI framework for interactive web dashboard
  - WebSocket client for streaming real-time data
  - psycopg2 for database queries
  - ECharts for data visualization
  - asyncio for asynchronous operations
  - Base64 encoding for PNG export

- SERVICE ARCHITECTURE:
  - Database query layer for historical events
  - WebSocket listener for real-time measurements
  - Event table display with filtering
  - Real-time chart visualization
  - Admin login system
  - PNG export functionality

- FEATURES:
  - **Recent Events Section**:
    - 3 tables displaying events by type (Earthquake, Conventional Explosion, Nuclear-like)
    - Auto-refresh every 5 seconds
    - Sensor filtering dropdown (All sensors or individual sensor-01 to sensor-12)
    - Refresh button for manual reload

  - **Real-time Measurements Viewer** (accessible via button):
    - Live sensor data streaming via WebSocket
    - Up to 500-point live data buffer in memory
    - 200-point chart display with smart decimation
    - Sensor-specific filtering
    - PNG export for charts

  - **Admin Panel** (requires login with admin/admin):
    - Login button visible to all users
    - Logout button visible after authentication
    - Show Replicas button (admin only) displays replica health status
    - Replica status indicator (Active / Inactive)

  - **Auto-refresh Mechanism**:
    - Event tables update every 5 seconds from database
    - Real-time measurements stream from broker continuously

- ENDPOINTS (WebSocket):
  - Subscribe to sensor measurements stream
  - Receive real-time measurement objects: {sensor_id, value, timestamp}

- PAGES:
  | Name | Description | Related Microservice | User Stories |
  | --- | --- | --- | --- |
  | Dashboard | Displays recent seismic events with filtering and statistics | Broker, Database | 1, 2, 3 |
  | Real-time Viewer | Live measurements with charts and sensor filtering | Broker | 4 |
  | Admin Panel | Login system, replica monitoring, chart export | Broker, Database | 5, 6, 7 |

---

## CONTAINER_NAME: Simulator

### DESCRIPTION:
Generates synthetic seismic signals simulating 12 parallel sensor channels for system testing and development.

### PORTS:
8080 (HTTP status)

### DESCRIPTION:
The Simulator container generates realistic synthetic seismic signals across 12 sensor channels. It simulates both normal background noise and event-specific frequency patterns to enable comprehensive system testing and demonstration of the frequency classification algorithm.

### MICROSERVICES:

#### MICROSERVICE: simulator
- TYPE: data generator
- DESCRIPTION: Generates synthetic seismic signals on 12 sensor channels with realistic noise and event patterns.
- PORTS: 8080
- TECHNOLOGICAL SPECIFICATION:
  - Python 3.11
  - numpy for signal generation
  - Realistic noise patterns and frequency distributions
  - Event simulation with controlled frequency bands

