# Docker Contract

This document describes the runtime environment variables supported by the simulator container.

The container listens on:

```text
0.0.0.0:8080
```

Full run command:

```bash
docker run --rm -p 8080:8080 \
  -e SAMPLING_RATE_HZ=20 \
  -e AUTO_SHUTDOWN_ENABLED=true \
  -e AUTO_SHUTDOWN_MIN_SECONDS=30 \
  -e AUTO_SHUTDOWN_MAX_SECONDS=90 \
  seismic-signal-simulator:multiarch_v1
```

or simply:

```bash
docker run --rm -p 8080:8080 seismic-signal-simulator:multiarch_v1
```

## Environment Variables

### `SAMPLING_RATE_HZ`

- Type: float
- Default in image: `20.0`
- Purpose: controls the sampling frequency for all sensor streams
- Effect: the simulator generates one sample every `1 / SAMPLING_RATE_HZ` seconds

Examples:

- `SAMPLING_RATE_HZ=20` means one sample every `50 ms`
- `SAMPLING_RATE_HZ=10` means one sample every `100 ms`
- `SAMPLING_RATE_HZ=40` means one sample every `25 ms`

Validation:

- must be parseable as a float
- invalid values stop the container at startup

### `AUTO_SHUTDOWN_ENABLED`

- Type: boolean
- Default in image: `true`
- Purpose: enables or disables background automatic shutdown generation
- Effect:
  - `true`: the simulator may emit automatic shutdown commands
  - `false`: shutdown commands are generated only by hidden instructor/manual triggers

Accepted values:

- truthy: `true`, `1`, `yes`, `on`
- falsy: `false`, `0`, `no`, `off`

Validation:

- any other value stops the container at startup

### `AUTO_SHUTDOWN_MIN_SECONDS`

- Type: float
- Default in image: `30.0`
- Purpose: lower bound of the random delay before an automatic shutdown
- Effect: automatic shutdowns never happen earlier than this value

Validation:

- must be parseable as a float
- invalid values stop the container at startup

### `AUTO_SHUTDOWN_MAX_SECONDS`

- Type: float
- Default in image: `90.0`
- Purpose: upper bound of the random delay before an automatic shutdown
- Effect: each automatic shutdown waits a random time in:

```text
[AUTO_SHUTDOWN_MIN_SECONDS, AUTO_SHUTDOWN_MAX_SECONDS]
```

Normalization rule:

- if `AUTO_SHUTDOWN_MAX_SECONDS < AUTO_SHUTDOWN_MIN_SECONDS`, the simulator effectively uses the minimum value for both bounds

Validation:

- must be parseable as a float
- invalid values stop the container at startup

## Variables Set in the Image but Not Part of the Public Simulator Contract

These are standard Python container settings and are not intended as exam-facing simulator controls.

## Startup Behavior

At container startup:

1. The container reads the environment variables.
2. The simulator validates and parses them.
3. If parsing fails, startup fails immediately.
4. If parsing succeeds, the simulator starts on port `8080`.
