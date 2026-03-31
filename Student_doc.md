# FONCHI - Distributed Seismic Monitoring System

## SYSTEM DESCRIPTION:

Fonchi is a distributed real-time seismic signal processing and monitoring system designed to detect and classify seismic events. The system uses a Master-Broker-Slave architecture with frequency analysis to classify events as earthquakes, conventional explosions, nuclear-like events, or base noise. Multiple sensor replicas process signals in parallel, with a centralized broker collecting data and a PostgreSQL database storing analysis results. A real-time NiceGUI frontend displays events, measurements, and replica status through WebSocket streaming.

## USER STORIES:

1) As a Monitor Operator, I want to see real-time seismic events so that I can track seismic activity
2) As a Monitor Operator, I want to filter events by sensor so that I can analyze specific sensor data
3) As a Monitor Operator, I want to view historical events from the database so that I can analyze past seismic trends
4) As a Monitor Operator, I want to see real-time measurements with live charts so that I can visualize sensor data
5) As an Admin, I want to log in to access administrative features so that I can manage system status
6) As an Admin, I want to view active replicas so that I can monitor system health
7) As an Admin, I want to download charts as PNG so that I can preserve analysis results
8) As a System Architect, I want seismic events classified by frequency so that I can differentiate event types
9) As a System Architect, I want signal processing in parallel across multiple replicas so that I can ensure system reliability
10) As a System Architect, I want persistent storage of analyzed events so that I can maintain historical records

## CONTAINERS:

## CONTAINER_NAME: Broker

### DESCRIPTION:
Manages WebSocket connections, coordinates Master-Broker-Slave communication, handles real-time data streaming, and maintains socket-based synchronization with replicas.

### USER STORIES:
1) As a Monitor Operator, I want to see real-time seismic events so that I can track seismic activity
2) As a Monitor Operator, I want to filter events by sensor so that I can analyze specific sensor data
4) As a Monitor Operator, I want to see real-time measurements with live charts so that I can visualize sensor data
9) As a System Architect, I want signal processing in parallel across multiple replicas so that I can ensure system reliability

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

- KEY FEATURES:
  - Real-time WebSocket streaming at ~50 messages per log cycle
  - Replica health monitoring with active_replicas state tracking
  - ACK-based reliability protocol for replica coordination
  - Automatic leader election among replicas
  - Broadcast of sensor data to all connected frontend clients

---

## CONTAINER_NAME: Replica

### DESCRIPTION:
Processes seismic signals using FFT frequency analysis, classifies events, communicates with broker via TCP socket, and stores results in PostgreSQL database.

### USER STORIES:
1) As a Monitor Operator, I want to see real-time seismic events so that I can track seismic activity
8) As a System Architect, I want seismic events classified by frequency so that I can differentiate event types
9) As a System Architect, I want signal processing in parallel across multiple replicas so that I can ensure system reliability
10) As a System Architect, I want persistent storage of analyzed events so that I can maintain historical records

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

- KEY FEATURES:
  - 12 sensor channels processed in parallel
  - Real-time FFT analysis with frequency classification
  - Event storage: sensor_id, event_type, startstamp, endstamp, frequency
  - TCP communication with heartbeat and ACK validation
  - Replica state reporting to broker

- ENDPOINTS (via TCP Socket):
  - Send classified event to broker (event_type, sensor_id, frequency, timestamps)
  - Receive ACK confirmation from broker
  - Report replica status to broker for health monitoring

---

## CONTAINER_NAME: Database

### DESCRIPTION:
Persistent storage for all analyzed seismic events, providing historical data for analysis and reporting.

### USER STORIES:
3) As a Monitor Operator, I want to view historical events from the database so that I can analyze past seismic trends
10) As a System Architect, I want persistent storage of analyzed events so that I can maintain historical records

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
1) As a Monitor Operator, I want to see real-time seismic events so that I can track seismic activity
2) As a Monitor Operator, I want to filter events by sensor so that I can analyze specific sensor data
3) As a Monitor Operator, I want to view historical events from the database so that I can analyze past seismic trends
4) As a Monitor Operator, I want to see real-time measurements with live charts so that I can visualize sensor data
5) As an Admin, I want to log in to access administrative features so that I can manage system status
6) As an Admin, I want to view active replicas so that I can monitor system health
7) As an Admin, I want to download charts as PNG so that I can preserve analysis results

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
    - 🔐 Login button visible to all users
    - 🔓 Logout button visible after authentication
    - 📊 Show Replicas button (admin only) displays replica health status
    - Replica status indicator (🟢 Active / 🔴 Inactive)

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

---

## SYSTEM ARCHITECTURE OVERVIEW:

### Data Flow:
1. **Simulator** generates synthetic seismic signals on 12 sensor channels
2. **Replicas** receive signals, perform FFT analysis, classify events
3. **Broker** aggregates results from replicas via TCP socket protocol
4. **Database** persists classified events for historical access
5. **Frontend** queries database for event display and streams real-time measurements via WebSocket

### Communication Protocols:
- **Broker ↔ Replicas**: TCP socket with ACK protocol and leader election
- **Broker ↔ Frontend**: WebSocket for real-time measurement streaming
- **Frontend ↔ Database**: Direct PostgreSQL queries
- **Replicas ↔ Database**: Direct event insertion

### Scalability:
- 5 parallel replicas for distributed signal processing
- Master-Broker-Slave architecture with automatic leader election
- Up to 500 real-time data points maintained in frontend buffer
- Indexed database queries with composite keys for fast retrieval

### Performance:
- ~50 messages per log cycle from broker
- 14450+ real-time messages flowing per session
- 1400+ events stored and queryable from database
- 200-point chart display with smart decimation for browser performance
- 5-second auto-refresh interval for event tables
