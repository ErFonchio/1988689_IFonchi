CREATE TABLE IF NOT EXISTS events (
    sensor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    frequency DOUBLE PRECISION NOT NULL,
    amplitude DOUBLE PRECISION,
    PRIMARY KEY (sensor_id, timestamp)
);

CREATE INDEX idx
ON events(sensor_id, timestamp);