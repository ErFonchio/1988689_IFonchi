# API Contract

This document describes only the HTTP, SSE, and WebSocket contract exposed by the seismic signal simulator.

Base URL:

```text
http://localhost:8080
```

## Overview

The API exposes:

- sensor discovery
- live time-domain sensor streams over WebSocket
- a shared SSE control stream for shutdown commands
- manual instructor/testing triggers for sensor events and shutdowns

## DTOs

### `Coordinates`

```json
{
  "latitude": 45.4642,
  "longitude": 9.19
}
```

### `SensorSummary`

Returned by discovery.

```json
{
  "id": "sensor-08",
  "name": "DC North Perimeter",
  "category": "datacenter",
  "region": "Replica Datacenter",
  "coordinates": {
    "latitude": 45.4642,
    "longitude": 9.19
  },
  "measurement_unit": "mm/s",
  "sampling_rate_hz": 20.0,
  "websocket_url": "/api/device/sensor-08/ws"
}
```

Field meaning:

- `id`: stable sensor identifier
- `name`: human-readable name
- `category`: either `field` or `datacenter`
- `region`: logical geographic area
- `coordinates`: sensor position
- `measurement_unit`: always `mm/s`
- `sampling_rate_hz`: per-sensor stream sampling rate
- `websocket_url`: WebSocket endpoint for that sensor

### `SensorMeasurement`

Returned continuously by sensor streams.

```json
{
  "timestamp": "2026-03-25T00:00:00.000000+00:00",
  "value": 0.123456
}
```

Field meaning:

- `timestamp`: UTC ISO-8601 timestamp of the sample
- `value`: signed ground velocity in `mm/s`

### `ControlOpenEvent`

First SSE event emitted by `/api/control`.

```json
{
  "connectedAt": "2026-03-25T00:00:00.000000+00:00",
  "controlStreamConnections": 3
}
```

### `ControlHeartbeatEvent`

Emitted periodically when no shutdown command is pending.

```json
{
  "timestamp": "2026-03-25T00:00:15.000000+00:00",
  "controlStreamConnections": 3
}
```

### `ShutdownCommand`

Emitted as an SSE `command` event on `/api/control`.

```json
{
  "command": "SHUTDOWN"
}
```

### `SensorEventRequest`

Request body for manual event injection.

```json
{
  "event_type": "earthquake"
}
```

Field rules:

- `event_type`: required, one of:
  - `earthquake`
  - `conventional_explosion`
  - `nuclear_like`
  - `calibration_pulse`
  - `datacenter_shutdown_disturbance`

### `ActiveSensorEvent`

Returned inside manual event injection and shutdown responses.

```json
{
  "eventId": "evt-123456789abc",
  "eventType": "earthquake",
  "frequencyHz": 1.6,
  "amplitude": 4.0,
  "durationSeconds": 8.0,
  "startsAt": "2026-03-25T00:00:00.000000+00:00",
  "endsAt": "2026-03-25T00:00:08.000000+00:00",
  "label": null
}
```

### `SensorEventResponse`

Response body for `POST /api/admin/sensors/{sensor_id}/events`.

```json
{
  "sensorId": "sensor-01",
  "event": {
    "eventId": "evt-123456789abc",
    "eventType": "earthquake",
    "frequencyHz": 1.6,
    "amplitude": 4.0,
    "durationSeconds": 8.0,
    "startsAt": "2026-03-25T00:00:00.000000+00:00",
    "endsAt": "2026-03-25T00:00:08.000000+00:00",
    "label": null
  },
  "samplingRateHz": 20.0
}
```

### `ManualShutdownResponse`

Response body for `POST /api/admin/shutdown`.

```json
{
  "command": {
    "command": "SHUTDOWN"
  },
  "reason": "manual_shutdown",
  "issuedAt": "2026-03-25T00:00:00.000000+00:00",
  "controlStreamConnections": 5,
  "generatedSensorEvent": {
    "sensorId": "sensor-10",
    "event": {
      "eventId": "evt-123456789abc",
      "eventType": "datacenter_shutdown_disturbance",
      "frequencyHz": 6.5,
      "amplitude": 5.0,
      "durationSeconds": 5.0,
      "startsAt": "2026-03-25T00:00:00.000000+00:00",
      "endsAt": "2026-03-25T00:00:05.000000+00:00",
      "label": "manual_shutdown disturbance"
    },
    "samplingRateHz": 20.0
  }
}
```

### `HealthResponse`

Response body for `GET /health`.

```json
{
  "status": "ok",
  "measurementUnit": "mm/s",
  "samplingRateHz": 20.0,
  "totalSensors": 12,
  "datacenterSensors": 5,
  "autoShutdownEnabled": true,
  "autoShutdownMinSeconds": 30.0,
  "autoShutdownMaxSeconds": 90.0,
  "controlStreamConnections": 5,
  "generatedAt": "2026-03-25T00:00:00.000000+00:00"
}
```

## Endpoints

### `GET /health`

Purpose: lightweight health check
- exposes active runtime configuration

Response DTO:

- `HealthResponse`

### `GET /docs`

Purpose: OpenAPI Swagger UI for the student-facing API

### `GET /openapi.json`

Purpose: machine-readable OpenAPI document for the student-facing API

### `GET /api/devices/`

Purpose: sensor discovery

Response DTO:

- array of `SensorSummary`

### `WS /api/device/{sensor_id}/ws`

Purpose: WebSocket stream for a single sensor

Path params:

- `sensor_id`: sensor identifier from discovery

Message DTO:

- `SensorMeasurement`

Error cases:

- connection rejected if sensor does not exist

### `GET /api/control`

Purpose: shared SSE control stream used by processing replicas

SSE event types:

- `control-open`
- `heartbeat`
- `command`

SSE data DTOs:

- `ControlOpenEvent`
- `ControlHeartbeatEvent`
- `ShutdownCommand`

Behavior:

- every listener subscribes to the same control endpoint
- when a shutdown is triggered, exactly one connected listener receives `{"command":"SHUTDOWN"}`
- if no command is pending, heartbeat events keep the stream alive

### `POST /api/admin/sensors/{sensor_id}/events`

Purpose: manually inject a predefined event on a sensor

Path params:

- `sensor_id`: target sensor identifier

Request DTO:

- `SensorEventRequest`

Response DTO:

- `SensorEventResponse`

Behavior:

- the request only needs `event_type`
- duration, amplitude, and frequency are taken from the simulator defaults for that event type

Error cases:

- `404` if sensor does not exist
- `422` if the request body is invalid

### `POST /api/admin/shutdown`

Purpose: manually trigger one shutdown command on the shared control stream

Response DTO:

- `ManualShutdownResponse`

Behavior:

- one active listener on `/api/control` receives `{"command":"SHUTDOWN"}`
- one datacenter sensor also receives a synthetic `datacenter_shutdown_disturbance` event

Error cases:

- `409` if there are no active control-stream listeners
