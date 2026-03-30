CREATE TABLE IF NOT EXISTS events (
    sensor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    frequency DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (sensor_id, timestamp)
);

CREATE TABLE IF NOT EXISTS measurements (
    sensor_id TEXT NOT NULL,
    sensor_value  double precision NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (sensor_id, timestamp)
);

CREATE INDEX idx
ON events(sensor_id, timestamp);