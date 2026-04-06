import copy
import logging
import os
import threading
import time
from unittest import mock

import numpy
import pytest

from ophyd import get_cl
from ophyd.areadetector.paths import EpicsPathSignal
from ophyd.signal import (
    DerivedSignal,
    EpicsSignal,
    EpicsSignalNoValidation,
    EpicsSignalRO,
    InternalSignal,
    InternalSignalError,
    Signal,
)
from ophyd.status import wait
from ophyd.utils import AlarmSeverity, AlarmStatus, ReadOnlyError

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def ro_signal(cleanup, signal_test_ioc):
    sig = EpicsSignalRO(signal_test_ioc.pvs["pair_rbv"], name="pair_rbv")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def nv_signal(cleanup, signal_test_ioc):
    sig = EpicsSignalNoValidation(signal_test_ioc.pvs["pair_set"], name="pair_set")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def bool_enum_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["bool_enum"], name="bool_enum")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def rw_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["read_write"], name="read_write")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def pair_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(
        read_pv=signal_test_ioc.pvs["pair_rbv"],
        write_pv=signal_test_ioc.pvs["pair_set"],
        name="pair",
    )
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def motor_pair_signal(cleanup, motor):
    sig = EpicsSignal(
        write_pv=motor.user_setpoint.pvname, read_pv=motor.user_readback.pvname
    )
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def set_severity_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["set_severity"], name="set_severity")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def alarm_status_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["alarm_status"], name="alarm_status")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


def test_signal_base():
    start_t = time.time()

    name = "test"
    value = 10.0
    signal = Signal(name=name, value=value, timestamp=start_t)
    signal.wait_for_connection()

    assert signal.connected
    assert signal.name == name
    with pytest.warns(UserWarning):
        assert signal.value == value
    assert signal.get() == value
    assert signal.timestamp == start_t

    info = dict(called=False)

    def _sub_test(**kwargs):
        info["called"] = True
        info["kw"] = kwargs

    signal.subscribe(_sub_test, run=False, event_type=signal.SUB_VALUE)
    assert not info["called"]

    signal.value = value
    signal.clear_sub(_sub_test)

    signal.subscribe(_sub_test, run=False, event_type=signal.SUB_VALUE)
    signal.clear_sub(_sub_test, event_type=signal.SUB_VALUE)

    kw = info["kw"]
    assert "value" in kw
    assert "timestamp" in kw
    assert "old_value" in kw

    assert kw["value"] == value
    assert kw["old_value"] == value
    assert kw["timestamp"] == signal.timestamp

    # readback callback for soft signal
    info = dict(called=False)
    signal.subscribe(_sub_test, event_type=Signal.SUB_VALUE, run=False)
    assert not info["called"]
    signal.put(value + 1)
    assert info["called"]

    signal.clear_sub(_sub_test)
    kw = info["kw"]

    assert "value" in kw
    assert "timestamp" in kw
    assert "old_value" in kw

    assert kw["value"] == value + 1
    assert kw["old_value"] == value
    assert kw["timestamp"] == signal.timestamp

    signal.trigger()
    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))


def test_signal_copy():
    start_t = time.time()

    name = "test"
    value = 10.0
    signal = Signal(name=name, value=value, timestamp=start_t)
    sig_copy = copy.copy(signal)

    assert signal.name == sig_copy.name
    with pytest.warns(UserWarning):
        assert signal.value == sig_copy.value
    assert signal.get() == sig_copy.get()
    assert signal.timestamp == sig_copy.timestamp


def test_signal_describe_fail():
    """
    Test Signal.describe() exception handling in the
    case where a Signal's value is not bluesky-friendly.
    """
    signal = Signal(name="the_none_signal", value=None)
    with pytest.raises(ValueError) as excinfo:
        signal.describe()
    assert "failed to describe 'the_none_signal' with value 'None'" in str(
        excinfo.value
    )


def test_internalsignal_write_from_internal():
    test_signal = InternalSignal(name="test_signal")
    for value in range(10):
        test_signal.put(value, internal=True)
        assert test_signal.get() == value
    for value in range(10):
        test_signal.set(value, internal=True).wait()
        assert test_signal.get() == value


def test_internalsignal_write_protection():
    test_signal = InternalSignal(name="test_signal")
    for value in range(10):
        with pytest.raises(InternalSignalError):
            test_signal.put(value)
        with pytest.raises(InternalSignalError):
            test_signal.set(value)


def test_epicssignal_readonly(cleanup, signal_test_ioc):
    signal = EpicsSignalRO(signal_test_ioc.pvs["read_only"])
    cleanup.add(signal)
    signal.wait_for_connection()
    print("EpicsSignalRO.metadata=", signal.metadata)
    signal.get()

    assert not signal.write_access
    assert signal.read_access

    with pytest.raises(ReadOnlyError):
        signal.value = 10

    with pytest.raises(ReadOnlyError):
        signal.put(10)

    with pytest.raises(ReadOnlyError):
        signal.set(10)

    # vestigial, to be removed
    with pytest.raises(AttributeError):
        signal.setpoint_ts

    # vestigial, to be removed
    with pytest.raises(AttributeError):
        signal.setpoint

    signal.precision
    signal.timestamp
    signal.limits

    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))
    time.sleep(0.2)


def test_epicssignal_novalidation(nv_signal):
    print("EpicsSignalNoValidation.metadata=", nv_signal.metadata)

    nv_signal.put(10)
    st = nv_signal.set(11)

    assert st.done

    nv_signal.get()
    nv_signal.read()

    nv_signal.describe()
    nv_signal.describe_configuration()

    nv_signal.read_configuration()


def test_epicssignal_readwrite_limits(pair_signal):
    signal = pair_signal
    signal.use_limits = True
    signal.check_value((signal.low_limit + signal.high_limit) / 2)

    with pytest.raises(ValueError):
        signal.check_value(None)

    with pytest.raises(ValueError):
        signal.check_value(signal.low_limit - 1)

    with pytest.raises(ValueError):
        signal.check_value(signal.high_limit + 1)


def test_epicssignal_readwrite(signal_test_ioc, pair_signal):
    pair_signal.use_limits = True
    signal = pair_signal

    assert signal.setpoint_pvname == signal_test_ioc.pvs["pair_set"]
    assert signal.pvname == signal_test_ioc.pvs["pair_rbv"]
    signal.get()

    time.sleep(0.2)

    value = 10
    signal.value = value
    signal.put(value)
    assert signal.setpoint == value
    signal.setpoint_ts

    signal.limits
    signal.precision
    signal.timestamp

    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))
    time.sleep(0.2)


def test_epicssignal_waveform(cleanup, signal_test_ioc):
    called = False

    def update_cb(value=None, **kwargs):
        nonlocal called
        assert len(value) > 1
        called = True

    signal = EpicsSignal(signal_test_ioc.pvs["waveform"], string=True)
    cleanup.add(signal)
    signal.wait_for_connection()

    sub = signal.subscribe(update_cb, event_type=signal.SUB_VALUE)
    assert len(signal.get()) > 1
    # force the current thread to allow other threads to run to service
    # subscription
    time.sleep(0.2)
    assert called
    signal.unsubscribe(sub)


def test_no_connection(cleanup, signal_test_ioc):
    sig = EpicsSignal("does_not_connect")
    cleanup.add(sig)

    with pytest.raises(TimeoutError):
        sig.wait_for_connection()

    sig = EpicsSignal("does_not_connect")
    cleanup.add(sig)

    with pytest.raises(TimeoutError):
        sig.put(0.0)

    with pytest.raises(TimeoutError):
        sig.get()

    sig = EpicsSignal(signal_test_ioc.pvs["read_only"], write_pv="does_not_connect")
    cleanup.add(sig)
    with pytest.raises(TimeoutError):
        sig.wait_for_connection()


def test_enum_strs(bool_enum_signal):
    assert bool_enum_signal.enum_strs == ("Off", "On")


def test_enum_set_wait(cleanup, signal_test_ioc):
    """set().wait() on an enum PV must complete without timeout.

    Regression test: epicsrs backend returned '1' (str) instead of 1 (int)
    for enum readback, causing _set_and_wait to spin forever comparing
    1 != '1'.
    """
    sig = EpicsSignal(signal_test_ioc.pvs["bool_enum"], name="bool_enum_sw")
    cleanup.add(sig)
    sig.wait_for_connection()

    # Ensure starting at 0
    sig.set(0).wait(timeout=5)
    assert sig.get() in (0, "Off")

    # set to 1 and wait — this timed out before the fix
    sig.set(1).wait(timeout=5)
    assert sig.get() in (1, "On")

    # round-trip back
    sig.set(0).wait(timeout=5)
    assert sig.get() in (0, "Off")


def test_enum_string_mode(cleanup, signal_test_ioc):
    """EpicsSignal(string=True) on enum PV: get() returns label, not '0'/'1'.

    Regression test: epicsrs monitor path delivered raw integer as char_value
    (e.g. '1') instead of resolving via enum_strs to 'On'.
    """
    sig = EpicsSignal(
        signal_test_ioc.pvs["bool_enum"], name="bool_enum_str", string=True
    )
    cleanup.add(sig)
    sig.wait_for_connection()

    sig.put(0, wait=True)
    val = sig.get()
    assert val in ("Off",), f"expected 'Off', got {val!r}"

    sig.put(1, wait=True)
    val = sig.get()
    assert val in ("On",), f"expected 'On', got {val!r}"

    # Monitor path: subscribe and verify label arrives
    received = []

    def cb(value=None, **kw):
        received.append(value)

    sig.subscribe(cb, event_type=sig.SUB_VALUE)
    sig.put(0, wait=True)
    time.sleep(0.5)  # allow monitor event to arrive

    # At least one callback should have a string label, not '0'
    str_values = [v for v in received if isinstance(v, str)]
    assert any(v in ("Off", "On") for v in str_values), (
        f"monitor delivered {received!r}, expected string labels"
    )


def test_char_waveform_as_string(cleanup, signal_test_ioc):
    """Char waveform PV with string=True returns decoded string, not '[97, 98, ...]'.

    Regression test: epicsrs _as_string() did not handle ftype=4 (CHAR)
    waveforms, returning str(list) instead of bytes.decode().
    """
    sig = EpicsSignal(
        signal_test_ioc.pvs["waveform"], name="waveform_str", string=True
    )
    cleanup.add(sig)
    sig.wait_for_connection()

    val = sig.get()
    assert isinstance(val, str), f"expected str, got {type(val).__name__}"
    assert len(val) > 0, "expected non-empty string"
    # The IOC sets waveform to [97, 98, 99] = "abc"
    assert val == "abc", f"expected 'abc', got {val!r}"


def test_path_signal_put_string(cleanup, signal_test_ioc):
    """String write to a path (char waveform) PV round-trips correctly.

    Regression test: epicsrs py_to_epics_value() only handled scalar types,
    so writing a string to a FTVL=CHAR waveform PV would fail.
    """
    sig = EpicsSignal(
        signal_test_ioc.pvs["path"],
        name="path_sig",
        string=True,
    )
    cleanup.add(sig)
    sig.wait_for_connection()

    test_path = "/tmp/test_data"
    sig.put(test_path, wait=True)
    time.sleep(0.2)

    val = sig.get()
    assert val == test_path, f"expected {test_path!r}, got {val!r}"



def test_float_precision_as_string(cleanup, signal_test_ioc):
    """Float PV with as_string=True respects precision field.

    Regression test: epicsrs returned full Python str(float) instead of
    formatting with the PV's PREC field.
    """
    sig = EpicsSignal(signal_test_ioc.pvs["read_write"], name="rw_prec")
    cleanup.add(sig)
    sig.wait_for_connection()

    sig.put(3.14159, wait=True)
    time.sleep(0.2)

    # Get precision — may be None or 0 for this test PV
    prec = sig.precision
    val_str = sig.get(as_string=True)
    assert isinstance(val_str, str), f"expected str, got {type(val_str).__name__}"

    if prec is not None and prec > 0:
        # Precision respected: "3.14" not "3.14159265..."
        assert len(val_str.split(".")[-1]) <= prec + 1
    else:
        # No precision — just verify it's a valid number string
        float(val_str)


def test_enum_put_string_label(cleanup, signal_test_ioc):
    """Writing enum label string (e.g. 'On') resolves to integer index.

    Regression test: epicsrs put("On") failed with TypeError because
    py_to_epics_value only accepted integers for enum PVs.
    """
    sig = EpicsSignal(signal_test_ioc.pvs["bool_enum"], name="bool_enum_put")
    cleanup.add(sig)
    sig.wait_for_connection()

    sig.put("Off", wait=True)
    assert sig.get() in (0, "Off")

    sig.put("On", wait=True)
    assert sig.get() in (1, "On")


def test_metadata_fields(cleanup, signal_test_ioc):
    """Verify all pyepics-compatible metadata fields are populated."""
    sig = EpicsSignal(signal_test_ioc.pvs["read_write"], name="rw_meta")
    cleanup.add(sig)
    sig.wait_for_connection()

    pv = sig._read_pv
    # Channel-level metadata
    assert pv.type != "unknown", f"type not set: {pv.type}"
    assert pv.count >= 1
    assert pv.host != ""
    assert pv.read_access is True
    assert pv.write_access is True

    # Timestamp
    args = pv._args
    assert args.get("timestamp") is not None
    assert args.get("status") is not None
    assert args.get("severity") is not None



def test_setpoint(rw_signal):
    rw_signal.get_setpoint()
    rw_signal.get_setpoint(as_string=True)


def test_epicssignalro():
    with pytest.raises(TypeError):
        # not in initializer parameters anymore
        EpicsSignalRO("test", write_pv="nope_sorry")


def test_describe(bool_enum_signal):
    sig = bool_enum_signal

    sig.put(1)
    desc = sig.describe()["bool_enum"]
    assert desc["dtype"] == "integer"
    assert desc["shape"] == []
    # assert 'precision' in desc
    assert desc["enum_strs"] == ("Off", "On")
    assert "upper_ctrl_limit" in desc
    assert "lower_ctrl_limit" in desc

    sig = Signal(name="my_pv")
    sig.put("Off")
    desc = sig.describe()["my_pv"]
    assert desc["dtype"] == "string"
    assert desc["shape"] == []

    sig.put(3.14)
    desc = sig.describe()["my_pv"]
    assert desc["dtype"] == "number"
    assert desc["shape"] == []

    import numpy as np

    sig.put(
        np.array(
            [
                1,
            ]
        )
    )
    desc = sig.describe()["my_pv"]
    assert desc["dtype"] == "array"
    assert desc["shape"] == [1]


def test_set_method():
    sig = Signal(name="sig")

    st = sig.set(28)
    wait(st)
    assert st.done
    assert st.success
    assert sig.get() == 28


def test_soft_derived():
    timestamp = 1.0
    value = "q"
    original = Signal(name="original", timestamp=timestamp, value=value)

    cb_values = []

    def callback(value=None, **kwargs):
        cb_values.append(value)

    derived = DerivedSignal(derived_from=original, name="derived")
    derived.subscribe(callback, event_type=derived.SUB_VALUE)

    assert derived.timestamp == timestamp
    assert derived.get() == value
    assert derived.timestamp == timestamp
    assert derived.describe()[derived.name]["derived_from"] == original.name
    assert derived.write_access == original.write_access
    assert derived.read_access == original.read_access

    new_value = "r"
    derived.put(new_value)
    assert original.get() == new_value
    assert derived.get() == new_value
    assert derived.timestamp == original.timestamp
    assert derived.limits == original.limits

    copied = copy.copy(derived)
    with pytest.warns(UserWarning):
        assert copied.derived_from.value == original.value
    assert copied.derived_from.timestamp == original.timestamp
    assert copied.derived_from.name == original.name

    derived.put("s")
    assert cb_values == ["r", "s"]

    called = []

    event = threading.Event()

    def meta_callback(*, connected, read_access, write_access, **kw):
        called.append(("meta", connected, read_access, write_access))
        event.set()

    derived.subscribe(meta_callback, event_type=derived.SUB_META, run=False)

    original._metadata["write_access"] = False
    original._run_subs(sub_type="meta", **original._metadata)

    event.wait(1)

    assert called == [("meta", True, True, False)]



@pytest.mark.motorsim
@pytest.mark.parametrize("put_complete", [True, False])
def test_epicssignal_set(motor_pair_signal, put_complete):
    sim_pv = motor_pair_signal
    sim_pv.put_complete = put_complete

    logging.getLogger("ophyd.signal").setLevel(logging.DEBUG)
    logging.getLogger("ophyd.utils.epics_pvs").setLevel(logging.DEBUG)
    print("tolerance=", sim_pv.tolerance)
    assert sim_pv.tolerance is not None

    start_pos = sim_pv.get()

    # move to +0.2 and check the status object
    target = sim_pv.get() + 0.2
    st = sim_pv.set(target, timeout=1, settle_time=0.001)
    wait(st, timeout=5)
    assert st.done
    assert st.success
    print("status 1", st)
    assert abs(target - sim_pv.get()) < 0.05

    # move back to -0.2, forcing a timeout with a low value
    target = sim_pv.get() - 0.2
    st = sim_pv.set(target, timeout=1e-6)
    time.sleep(0.5)
    print("status 2", st)
    assert st.done
    # epicsrs fire-and-forget put may not reach IOC before timeout
    # check, so the position may still be within tolerance
    if os.environ.get("TEST_CL") != "epicsrs":
        assert not st.success

    # keep the axis in position
    st = sim_pv.set(start_pos)
    wait(st, timeout=5)


statuses_and_severities = [
    (AlarmStatus.NO_ALARM, AlarmSeverity.NO_ALARM),
    (AlarmStatus.READ, AlarmSeverity.MINOR),
    (AlarmStatus.WRITE, AlarmSeverity.MAJOR),
    (AlarmStatus.HIHI, AlarmSeverity.INVALID),
    (AlarmStatus.NO_ALARM, AlarmSeverity.NO_ALARM),
]


@pytest.mark.parametrize("status, severity", statuses_and_severities)
def test_epicssignal_alarm_status(
    set_severity_signal, alarm_status_signal, pair_signal, status, severity
):
    alarm_status_signal.put(status, wait=True)
    set_severity_signal.put(severity, wait=True)

    pair_signal.get()
    assert pair_signal.alarm_status == status
    assert pair_signal.alarm_severity == severity

    pair_signal.get_setpoint()
    assert pair_signal.setpoint_alarm_status == status
    assert pair_signal.setpoint_alarm_severity == severity


@pytest.mark.parametrize("status, severity", statuses_and_severities)
def test_epicssignalro_alarm_status(
    set_severity_signal, alarm_status_signal, ro_signal, status, severity
):
    alarm_status_signal.put(status, wait=True)
    set_severity_signal.put(severity, wait=True)

    ro_signal.get()
    assert ro_signal.alarm_status == status
    assert ro_signal.alarm_severity == severity


def test_hints(cleanup, fake_motor_ioc):
    sig = EpicsSignalRO(fake_motor_ioc.pvs["setpoint"])
    cleanup.add(sig)
    assert sig.hints == {"fields": [sig.name]}


def test_epicssignal_sub_setpoint(cleanup, fake_motor_ioc):
    pvs = fake_motor_ioc.pvs
    pv = EpicsSignal(write_pv=pvs["setpoint"], read_pv=pvs["readback"], name="pv")
    cleanup.add(pv)

    setpoint_called = []
    setpoint_meta_called = []

    def sub_setpoint(old_value, value, **kwargs):
        setpoint_called.append((old_value, value))

    def sub_setpoint_meta(timestamp, **kwargs):
        setpoint_meta_called.append(timestamp)

    pv.subscribe(sub_setpoint, event_type=pv.SUB_SETPOINT)
    pv.subscribe(sub_setpoint_meta, event_type=pv.SUB_SETPOINT_META)

    pv.wait_for_connection()

    pv.put(1, wait=True)
    pv.put(2, wait=True)
    time.sleep(1.0)

    assert len(setpoint_called) >= 3
    assert len(setpoint_meta_called) >= 3


def test_epicssignal_get_in_callback(fake_motor_ioc, cleanup):
    pvs = fake_motor_ioc.pvs
    sig = EpicsSignal(write_pv=pvs["setpoint"], read_pv=pvs["readback"], name="motor")
    cleanup.add(sig)

    called = []

    def generic_sub(sub_type, **kwargs):
        called.append((sub_type, sig.get(), sig.get_setpoint()))

    for event_type in (
        sig.SUB_VALUE,
        sig.SUB_META,
        sig.SUB_SETPOINT,
        sig.SUB_SETPOINT_META,
    ):
        sig.subscribe(generic_sub, event_type=event_type)

    sig.wait_for_connection()

    sig.put(1, wait=True)
    sig.put(2, wait=True)
    time.sleep(0.5)

    print(called)
    # Arbitrary threshold, but if @klauer screwed something up again, this will
    # blow up
    assert len(called) < 20
    print("total", len(called))
    sig.unsubscribe_all()


@pytest.mark.motorsim
@pytest.mark.parametrize(
    "pvname, count",
    [
        ("sim:mtr1.RBV", 10),
        ("sim:mtr2.RBV", 10),
        ("sim:mtr1.RBV", 100),
        ("sim:mtr2.RBV", 100),
    ],
)
def test_epicssignal_pv_reuse(cleanup, pvname, count):
    signals = [EpicsSignal(pvname, name="sig") for i in range(count)]

    for sig in signals:
        cleanup.add(sig)
        sig.wait_for_connection(timeout=10)
        assert sig.connected
        assert sig.get(timeout=10) is not None

    if get_cl().name == "pyepics":
        assert len(set(id(sig._read_pv) for sig in signals)) == 1


@pytest.fixture(scope="function")
def path_signal(cleanup, signal_test_ioc):
    sig = EpicsPathSignal(
        signal_test_ioc.pvs["path"], name="path", path_semantics="posix"
    )
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.mark.parametrize(
    "paths",
    [
        ("C:\\some\\path\\here"),
        ("D:\\here\\is\\another\\"),
        ("C:/yet/another/path"),
        ("D:/more/paths/here/"),
    ],
)
def test_windows_paths(paths, path_signal):
    path_signal.path_semantics = "nt"
    path_signal.set(paths).wait(3)


@pytest.mark.parametrize("paths", [("/some/path/here"), ("/here/is/another/")])
def test_posix_paths(paths, path_signal):
    path_signal.set(paths).wait(3)


def test_path_semantics_exception():
    with pytest.raises(ValueError):
        EpicsPathSignal("TEST", path_semantics="not_a_thing")


def test_import_ro_signal_class():
    from ophyd import SignalRO as SignalRoFromPkg
    from ophyd.signal import SignalRO as SignalRoFromModule

    assert SignalRoFromPkg is SignalRoFromModule


def test_signal_dtype_shape_info(fake_motor_ioc, cleanup):
    pvs = fake_motor_ioc.pvs
    sig = EpicsSignal(write_pv=pvs["setpoint"], read_pv=pvs["readback"], name="motor")
    sig_desc = sig.describe()["motor"]
    assert sig_desc["dtype"] == "number"
    assert sig_desc["shape"] == []

    sig = EpicsSignal(
        write_pv=pvs["setpoint"], read_pv=pvs["readback"], name="motor", dtype=float
    )
    sig_desc = sig.describe()["motor"]
    assert sig_desc["dtype"] == "number"
    assert sig_desc["dtype_numpy"] == "float64"
    assert sig_desc["shape"] == []

    original = Signal(name="original")
    original_desc = original.describe()["original"]
    assert original_desc["dtype"] == "number"
    assert "dtype_numpy" not in original_desc
    assert original_desc["shape"] == []
    assert pytest.approx(original.get()) == 0.0
    original = Signal(name="original", value=1)
    original_desc = original.describe()["original"]
    assert original_desc["dtype"] == "integer"
    assert "dtype_numpy" not in original_desc
    assert original_desc["shape"] == []
    assert original.get() == 1
    original = Signal(name="original", value="On")
    original_desc = original.describe()["original"]
    assert original_desc["dtype"] == "string"
    assert "dtype_numpy" not in original_desc
    assert original_desc["shape"] == []
    assert original.get() == "On"
    original = Signal(name="original", dtype=numpy.uint16, shape=(2, 2))
    original_desc = original.describe()["original"]
    assert original_desc["dtype"] == "array"
    assert original_desc["dtype_numpy"] == "uint16"
    assert original_desc["shape"] == [2, 2]
    with pytest.raises(RuntimeError):
        original.get()
    original = Signal(
        name="original",
        value=numpy.array([[1, 2], [3, 4]]),
        dtype=numpy.uint16,
        shape=(2, 2),
    )
    original_desc = original.describe()["original"]
    assert original_desc["dtype"] == "array"
    assert original_desc["dtype_numpy"] == "uint16"
    assert original_desc["shape"] == [2, 2]
    test_arr = numpy.array([1, 2, 3, 4], dtype=numpy.uint16)
    test_arr.shape = (2, 2)
    numpy.testing.assert_equal(original.get(), test_arr)

    class TestDerivedSignal(DerivedSignal):
        def forward(self, value):
            return value / 2

        def inverse(self, value):
            return 2 * value

    derived = TestDerivedSignal(
        derived_from=original, name="derived", dtype=numpy.uint32, shape=(2, 2)
    )

    derived_desc = derived.describe()["derived"]
    assert derived_desc["dtype"] == "array"
    assert derived_desc["dtype_numpy"] == "uint32"
    assert derived_desc["shape"] == [2, 2]
    assert derived_desc["derived_from"] == original.name

    string_signal_with_value = Signal(
        name="string_signal", dtype="string", value="test"
    )
    desc = string_signal_with_value.describe()["string_signal"]
    assert desc["dtype"] == "string"
    assert "dtype_numpy" not in desc
    assert desc["shape"] == []
    assert string_signal_with_value.get() == "test"

    string_signal = Signal(name="string_signal", dtype="string")
    with mock.patch.object(
        string_signal, "get", return_value="StringSignal"
    ) as mocked_get:
        desc = string_signal.describe()["string_signal"]
    mocked_get.assert_called_once()
    assert desc["dtype"] == "string"
    assert "dtype_numpy" not in desc
    assert desc["shape"] == []

    with pytest.raises(TypeError):
        # bad default vs dtype
        Signal(name="bad_value", dtype="uint16", value=[0.3, 1])
    ok_conversion_default_to_dtype = Signal(
        name="ok_value", dtype="uint16", value=[1, 2]
    )
    assert ok_conversion_default_to_dtype._value_dtype_str == "uint16"
    with pytest.raises(TypeError):
        # bad default vs shape
        Signal(
            name="bad_value", dtype="int64", shape=(2, 2), value=[[1, 2, 3], [4, 5, 6]]
        )
    ok_default_shape = Signal(
        name="ok_value", dtype="int64", shape=(2, 2), value=[[1, 2], [3, 4]]
    )
    assert ok_default_shape._value_shape == (2, 2)


def test_signal_default_type():
    s = Signal(name="aardvark")
    assert type(s.read()["aardvark"]["value"]) is float
