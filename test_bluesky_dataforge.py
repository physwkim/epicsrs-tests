"""
bluesky-dataforge integration tests.

Tests AsyncMongoWriter against a real MongoDB instance.

Covers:
  - Step scan events written async to MongoDB
  - Fly scan EventPage bulk insert
  - Async vs sync write performance

Requires:
  - epics-rs mini-beamline IOC running (PV prefix: mini:)
  - MongoDB accessible (set MONGO_HOST env var, default: localhost)
"""

import os
import time

import numpy as np
from ophyd_epicsrs import EpicsRsContext
from ophyd import EpicsMotor, EpicsSignalRO, Device, Component as Cpt
from ophyd.status import DeviceStatus

from bluesky import RunEngine
from bluesky.plans import scan, fly
from bluesky_dataforge import AsyncMongoWriter
from pymongo import MongoClient

import threading


MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_URI = f"mongodb://{MONGO_HOST}:27017"
DB_NAME = "test_dataforge"


class PointDetector(Device):
    value = Cpt(EpicsSignalRO, 'DetValue_RBV', kind='hinted')


class MiniFlyer:
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


def _cleanup():
    MongoClient(MONGO_HOST, 27017).drop_database(DB_NAME)


def _get_db():
    return MongoClient(MONGO_HOST, 27017)[DB_NAME]


def _make_motor():
    mtr = EpicsMotor('mini:ph:mtr', name='ph_mtr')
    mtr.wait_for_connection(timeout=10)
    mtr.velocity.put(50.0)
    return mtr


def test_step_scan_async_write():
    """Step scan: 11 events written to MongoDB via AsyncMongoWriter."""
    _cleanup()
    mtr = _make_motor()
    det = PointDetector('mini:ph:', name='ph_det')
    det.wait_for_connection(timeout=10)

    RE = RunEngine({})
    writer = AsyncMongoWriter(MONGO_URI, DB_NAME)
    RE.subscribe(writer)

    RE(scan([det], mtr, -5, 5, 11))
    writer.flush()

    db = _get_db()
    assert db.run_start.count_documents({}) == 1
    assert db.event.count_documents({}) == 11
    assert db.run_stop.count_documents({}) == 1

    ev = db.event.find_one()
    assert 'ph_det_value' in ev['data']

    writer.close()
    _cleanup()


def test_fly_scan_event_page():
    """Fly scan: EventPage written to MongoDB."""
    _cleanup()
    mtr = _make_motor()

    RE = RunEngine({})
    writer = AsyncMongoWriter(MONGO_URI, DB_NAME)
    RE.subscribe(writer)

    flyer = MiniFlyer(mtr)
    mtr.move(-5.0, wait=True, timeout=30)
    flyer._target = 5.0

    RE(fly([flyer]))
    writer.flush()

    db = _get_db()
    assert db.run_start.count_documents({}) == 1
    assert db.event.count_documents({}) >= 1

    ev = db.event.find_one()
    assert 'motor_pos' in ev['data'] or 'mini_flyer_motor_pos' in ev['data']

    writer.close()
    _cleanup()


def test_async_vs_sync_performance():
    """AsyncMongoWriter should not add overhead to scan time."""
    _cleanup()
    mtr = _make_motor()
    det = PointDetector('mini:ph:', name='ph_det')
    det.wait_for_connection(timeout=10)

    # Async
    RE = RunEngine({})
    writer = AsyncMongoWriter(MONGO_URI, DB_NAME)
    RE.subscribe(writer)

    t0 = time.perf_counter()
    RE(scan([det], mtr, -5, 5, 21))
    scan_async = time.perf_counter() - t0
    writer.flush()
    total_async = time.perf_counter() - t0
    writer.close()
    _cleanup()

    # Sync baseline (collect only, no DB write)
    RE2 = RunEngine({})
    docs = []
    RE2.subscribe(lambda name, doc: docs.append((name, doc)))

    t0 = time.perf_counter()
    RE2(scan([det], mtr, -5, 5, 21))
    scan_sync = time.perf_counter() - t0

    # Async scan time should be within 50% of sync (no significant overhead)
    overhead = (scan_async - scan_sync) / scan_sync if scan_sync > 0 else 0
    assert overhead < 0.5, f"async overhead {overhead:.0%} too high"
