# epicsrs-integration-tests

Integration tests for [ophyd-epicsrs](https://github.com/physwkim/ophyd-epicsrs) and [bluesky-dataforge](https://github.com/physwkim/bluesky-dataforge).

Tests run against a live [epics-rs](https://github.com/epics-rs/epics-rs) mini-beamline IOC and optionally a MongoDB instance.

## Prerequisites

- **Rust toolchain** (1.85+) — required to build ophyd-epicsrs from source
- **Python** 3.12+
- **epics-rs mini-beamline IOC** running with PV prefix `mini:`
- **MongoDB** (optional, required for bluesky-dataforge tests)

### Start the mini-beamline IOC

```bash
cd /path/to/epics-rs
cargo run --release -p mini-beamline
```

Verify PVs are accessible:

```bash
caget mini:current mini:ph:mtr.RBV
```

### Start MongoDB (optional)

```bash
docker run -d -p 27017:27017 mongo:4.4
```

## Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Note**: `ophyd-epicsrs` builds a Rust native extension via [maturin](https://www.maturin.rs/). This requires a working Rust toolchain (`rustup`, `cargo`). The build happens automatically during `pip install`.

## Run tests

### All tests (requires IOC + MongoDB)

```bash
pytest -v
```

### ophyd-epicsrs only (requires IOC only)

```bash
pytest -v test_ophyd_epicsrs.py
```

### bluesky-dataforge only (requires IOC + MongoDB)

```bash
# If MongoDB is not on localhost:
MONGO_HOST=100.103.0.70 pytest -v test_bluesky_dataforge.py
```

### Run without pytest

```bash
QT_API=pyside6 MPLBACKEND=Agg python -m test_ophyd_epicsrs
```

## Test coverage

### test_ophyd_epicsrs.py

| Test | What it verifies |
|------|-----------------|
| `test_connect_read_move` | EpicsMotor connect, read, move(wait=True) |
| `test_step_scan` | Bluesky scan plan with motor + detector (11 points) |
| `test_fly_scan` | bulk_caget + collect_pages EventPage |
| `test_bulk_caget_performance` | Parallel read faster than sequential |
| `test_put_callback_timing` | put(wait=False) callback fires after write completes |
| `test_monitor_values` | Monitor callbacks deliver correct ordered values |
| `test_connection_callback` | Connection callback fires on connect |
| `test_bulk_caget_failed_pvs` | Failed PVs return None (not omitted) |
| `test_get_pv_connect` | get_pv(connect=True) blocks until connected |
| `test_move_wait_regression` | move(wait=True) works at fast and slow speeds |

### test_bluesky_dataforge.py

| Test | What it verifies |
|------|-----------------|
| `test_step_scan_async_write` | 11 events written to MongoDB via AsyncMongoWriter |
| `test_fly_scan_event_page` | EventPage from collect_pages stored in MongoDB |
| `test_async_vs_sync_performance` | Async write adds < 50% scan time overhead |

## Pinned versions

Exact commits are pinned in `requirements.txt` to ensure reproducibility:

| Package | Version / Commit |
|---------|-----------------|
| ophyd | `physwkim/ophyd@9359f19` (feature/epicsrs-backend) |
| ophyd-epicsrs | `v0.2.0` |
| bluesky-dataforge | `physwkim/bluesky-dataforge@2254ddc` |

## Related projects

- [epics-rs](https://github.com/epics-rs/epics-rs) — Pure Rust EPICS implementation
- [ophyd-epicsrs](https://github.com/physwkim/ophyd-epicsrs) — Rust CA backend for ophyd
- [bluesky-dataforge](https://github.com/physwkim/bluesky-dataforge) — Async MongoDB writer
- [ophyd](https://github.com/physwkim/ophyd) — Fork with epicsrs control layer
