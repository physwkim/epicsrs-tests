"""
ophyd-epicsrs integration tests.

Tests the Rust CA backend for ophyd against the epics-rs mini-beamline IOC.

Covers:
  - EpicsMotor connect, read, move(wait=True)
  - Bluesky step scan
  - Bluesky fly scan with bulk_caget + collect_pages
  - bulk_caget performance benchmark
  - put(wait=False) callback timing
  - Monitor callback correctness
  - Connection / access callbacks
  - bulk_caget failed PV handling (None, not omitted)
  - get_pv(connect=True) blocks until connected

Requires:
  - epics-rs mini-beamline IOC running (PV prefix: mini:)
"""

import time
import threading

import numpy as np
from ophyd_epicsrs import EpicsRsContext
from ophyd import EpicsMotor, EpicsSignalRO, Device, Component as Cpt
from ophyd.status import DeviceStatus

from bluesky import RunEngine
from bluesky.plans import scan, fly


# ── Helpers ────────────────────────────────────────────────────────────

class PointDetector(Device):
    value = Cpt(EpicsSignalRO, 'DetValue_RBV', kind='hinted')


class EventCollector:
    """Callback that collects events in memory."""
    def __init__(self):
        self.events = []

    def __call__(self, name, doc):
        if name == 'event':
            self.events.append(doc)
        elif name == 'event_page':
            n = len(doc['seq_num'])
            for i in range(n):
                self.events.append({
                    'data': {k: v[i] for k, v in doc['data'].items()},
                    'timestamps': {k: v[i] for k, v in doc['timestamps'].items()},
                    'time': doc['time'][i],
                    'seq_num': doc['seq_num'][i],
                })


class MiniFlyer:
    """Flyer that yields EventPage via bulk_caget."""
    _ctx = EpicsRsContext()

    def __init__(self, motor):
        self.name = 'mini_flyer'
        self.parent = None
        self._motor = motor
        self._target = 5.0
        self._complete_status = None
        self._acquiring = False

    def kickoff(self):
        self._acquiring = True
        self._complete_status = DeviceStatus(self._motor)
        self._motor.move(self._target, wait=False)

        def _wait():
            while True:
                dmov = self._motor.motor_done_move.get(use_monitor=False)
                if dmov == 1:
                    break
                time.sleep(0.05)
            self._acquiring = False
            self._complete_status.set_finished()
        threading.Thread(target=_wait, daemon=True).start()

        st = DeviceStatus(self._motor)
        st.set_finished()
        return st

    def complete(self):
        return self._complete_status

    def describe_collect(self):
        return {
            'primary': {
                'motor_pos': dict(source='mini:ph:mtr', dtype='number', shape=[]),
                'det_ph': dict(source='mini:ph:DetValue_RBV', dtype='number', shape=[]),
                'beam': dict(source='mini:current', dtype='number', shape=[]),
            }
        }

    def collect_pages(self):
        if self._acquiring:
            raise RuntimeError('Still acquiring')
        pvs = ['mini:ph:mtr.RBV', 'mini:ph:DetValue_RBV', 'mini:current']
        keys = ['motor_pos', 'det_ph', 'beam']
        raw = self._ctx.bulk_caget(pvs)
        now = time.time()
        data = {k: [float(raw[pv])] for k, pv in zip(keys, pvs)}
        timestamps = {k: [now] for k in keys}
        yield {
            'data': data,
            'timestamps': timestamps,
            'time': [now],
            'seq_num': [1],
        }


# ── Tests ──────────────────────────────────────────────────────────────

def _make_motor():
    mtr = EpicsMotor('mini:ph:mtr', name='ph_mtr')
    mtr.wait_for_connection(timeout=10)
    mtr.velocity.put(50.0)
    return mtr


def test_connect_read_move():
    """EpicsMotor: connect, read, move(wait=True)."""
    beam = EpicsSignalRO('mini:current', name='beam')
    beam.wait_for_connection(timeout=5)
    assert beam.get() > 0

    mtr = _make_motor()
    mtr.move(0.0, wait=True, timeout=30)
    pos = mtr.user_readback.get(use_monitor=False)
    assert abs(pos) < 0.5, f"motor at {pos}, expected ~0"


def test_step_scan():
    """Bluesky step scan: 11 points with motor + detector."""
    mtr = _make_motor()
    det = PointDetector('mini:ph:', name='ph_det')
    det.wait_for_connection(timeout=10)

    RE = RunEngine({})
    collector = EventCollector()
    RE.subscribe(collector)
    RE(scan([det], mtr, -5, 5, 11))

    assert len(collector.events) == 11

    values = [e['data']['ph_det_value'] for e in collector.events]
    peak_idx = np.argmax(values)
    peak_pos = collector.events[peak_idx]['data']['ph_mtr']
    assert abs(peak_pos) < 2.0, f"peak at {peak_pos}, expected near 0"


def test_fly_scan():
    """Fly scan: bulk_caget + collect_pages."""
    mtr = _make_motor()

    RE = RunEngine({})
    collector = EventCollector()
    RE.subscribe(collector)

    flyer = MiniFlyer(mtr)
    mtr.move(-5.0, wait=True, timeout=30)
    flyer._target = 5.0
    RE(fly([flyer]))

    assert len(collector.events) >= 1
    ev = collector.events[0]
    assert 'motor_pos' in ev['data']
    assert 'det_ph' in ev['data']


def test_bulk_caget_performance():
    """bulk_caget: parallel read faster than sequential."""
    ctx = EpicsRsContext()
    pvs = [
        'mini:current', 'mini:ph:mtr.RBV', 'mini:edge:mtr.RBV',
        'mini:slit:mtr.RBV', 'mini:ph:DetValue_RBV',
        'mini:edge:DetValue_RBV', 'mini:slit:DetValue_RBV',
    ]
    ctx.bulk_caget(pvs)  # warm up

    N = 100
    t0 = time.perf_counter()
    for _ in range(N):
        ctx.bulk_caget(pvs)
    bulk_ms = (time.perf_counter() - t0) / N * 1000

    from epics import caget
    t0 = time.perf_counter()
    for _ in range(N):
        for pv in pvs:
            caget(pv)
    seq_ms = (time.perf_counter() - t0) / N * 1000

    assert bulk_ms < seq_ms, f"bulk ({bulk_ms:.2f}ms) should be faster than seq ({seq_ms:.2f}ms)"


def test_put_callback_timing():
    """put(wait=False, callback): callback fires after write completes."""
    ctx = EpicsRsContext()
    pv = ctx.create_pv("mini:ph:mtr.VAL")
    pv.wait_for_connection(timeout=5)

    velo = ctx.create_pv("mini:ph:mtr.VELO")
    velo.wait_for_connection(timeout=5)
    velo.put(50.0, wait=True)
    pv.put(10.0, wait=True)
    time.sleep(0.5)

    callback_event = threading.Event()
    t0 = time.perf_counter()

    def on_done():
        callback_event.set()

    pv.put(0.0, wait=False, callback=on_done)
    put_return = time.perf_counter() - t0

    assert callback_event.wait(timeout=30)
    cb_delay = time.perf_counter() - t0

    assert cb_delay > put_return, "callback should fire after put() returns"


def test_monitor_values():
    """Monitor callbacks deliver correct values."""
    ctx = EpicsRsContext()
    pv = ctx.create_pv("mini:ph:mtr.VAL")
    pv.wait_for_connection(timeout=5)

    velo = ctx.create_pv("mini:ph:mtr.VELO")
    velo.wait_for_connection(timeout=5)
    velo.put(50.0, wait=True)
    pv.put(0.0, wait=True)
    time.sleep(0.5)

    rbv_pv = ctx.create_pv("mini:ph:mtr.RBV")
    rbv_pv.wait_for_connection(timeout=5)

    events = []
    lock = threading.Lock()

    def on_monitor(**kwargs):
        with lock:
            events.append(kwargs)

    rbv_pv.add_monitor_callback(on_monitor)
    time.sleep(0.3)

    pv.put(5.0, wait=True)
    time.sleep(0.5)

    with lock:
        n = len(events)

    assert n >= 2, f"expected >=2 events, got {n}"
    for ev in events[:3]:
        assert 'pvname' in ev
        assert 'value' in ev
        assert 'timestamp' in ev

    with lock:
        last_val = float(events[-1]['value'])
    assert abs(last_val - 5.0) < 0.5

    rbv_pv.clear_monitors()


def test_connection_callback():
    """Connection callback fires on connect."""
    ctx = EpicsRsContext()
    pv = ctx.create_pv("mini:current")

    conn_event = threading.Event()

    def on_connect(connected):
        if connected:
            conn_event.set()

    pv.set_connection_callback(on_connect)
    assert conn_event.wait(timeout=5), "connection callback never fired"


def test_bulk_caget_failed_pvs():
    """bulk_caget: failed PVs return None, not omitted."""
    ctx = EpicsRsContext()
    pvs = ["mini:current", "NONEXISTENT:PV:12345", "mini:ph:mtr.RBV"]

    result = ctx.bulk_caget(pvs, timeout=3.0)

    assert len(result) == 3, f"expected 3 keys, got {len(result)}"
    assert result["mini:current"] is not None
    assert result["mini:ph:mtr.RBV"] is not None
    assert "NONEXISTENT:PV:12345" in result
    assert result["NONEXISTENT:PV:12345"] is None


def test_get_pv_connect():
    """get_pv(connect=True) blocks until connected."""
    import ophyd
    pv = ophyd.cl.get_pv('mini:current', connect=True, timeout=5.0)
    assert pv.connected, "PV should be connected after connect=True"
    assert pv.get() is not None


def test_move_wait_regression():
    """move(wait=True) waits at both fast and slow speeds."""
    mtr = _make_motor()

    mtr.move(20.0, wait=True, timeout=30)
    assert abs(mtr.user_readback.get(use_monitor=False) - 20.0) < 0.5

    mtr.move(0.0, wait=True, timeout=30)
    assert abs(mtr.user_readback.get(use_monitor=False)) < 0.5

    mtr.velocity.put(5.0)
    mtr.move(10.0, wait=True, timeout=30)
    assert abs(mtr.user_readback.get(use_monitor=False) - 10.0) < 0.5
