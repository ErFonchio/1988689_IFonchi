CREATE TABLE IF NOT EXISTS events (
    sensor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    startstamp TIMESTAMPTZ NOT NULL,
    endstamp TIMESTAMPTZ NOT NULL,
    frequency DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (sensor_id, startstamp, endstamp)
);

