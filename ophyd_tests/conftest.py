import logging
from types import SimpleNamespace

import pytest

from ophyd import Component as Cpt
from ophyd import EpicsMotor, EpicsSignal, EpicsSignalRO, Signal
from ophyd.utils.epics_pvs import AlarmSeverity, AlarmStatus

logger = logging.getLogger(__name__)

# Fixed prefixes for the combined caproto IOC (caproto_ioc.py)
MOTOR_PREFIX = "test:motor:"
SIGNAL_PREFIX = "test:signal:"
MCA_PREFIX = "test:mca:"
SCALER_PREFIX = "test:scaler:"


@pytest.fixture()
def hw(tmpdir):
    from ophyd.sim import hw

    return hw(str(tmpdir))


class CustomAlarmEpicsSignalRO(EpicsSignalRO):
    alarm_status = AlarmStatus.NO_ALARM
    alarm_severity = AlarmSeverity.NO_ALARM


class TestEpicsMotor(EpicsMotor):
    user_readback = Cpt(CustomAlarmEpicsSignalRO, ".RBV", kind="hinted")
    high_limit_switch = Cpt(Signal, value=0, kind="omitted")
    low_limit_switch = Cpt(Signal, value=0, kind="omitted")
    direction_of_travel = Cpt(Signal, value=0, kind="omitted")
    high_limit_value = Cpt(EpicsSignal, ".HLM", kind="config")
    low_limit_value = Cpt(EpicsSignal, ".LLM", kind="config")

    @user_readback.sub_value
    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        """Callback from EPICS, indicating a change in position"""
        super()._pos_changed(timestamp=timestamp, value=value, **kwargs)


@pytest.fixture(scope="function")
def motor(request, cleanup):
    sim_pv = "XF:31IDA-OP{Tbl-Ax:X1}Mtr"

    motor = TestEpicsMotor(sim_pv, name="epicsmotor", settle_time=0.1, timeout=10.0)
    cleanup.add(motor)

    print("Created EpicsMotor:", motor)
    motor.wait_for_connection()
    # Reset offset and limits to clean state before each test
    motor.user_offset.put(0, wait=True)
    motor.user_offset_dir.put(0, wait=True)
    motor.offset_freeze_switch.put(0, wait=True)
    motor.set_use_switch.put(0, wait=True)
    motor.low_limit_value.put(-100, wait=True)
    motor.high_limit_value.put(100, wait=True)
    motor.set(0).wait()

    return motor


@pytest.fixture(scope="module")
def ad_prefix():
    "AreaDetector prefix"
    prefixes = ["ADSIM:", "XF:31IDA-BI{Cam:Tbl}:"]

    for prefix in prefixes:
        test_pv = prefix + "TIFF1:PluginType_RBV"
        try:
            sig = EpicsSignalRO(test_pv)
            sig.wait_for_connection(timeout=2)
        except TimeoutError:
            ...
        else:
            print("areaDetector detected with prefix:", prefix)
            _prime_ad_plugins(prefix)
            return prefix
        finally:
            sig.destroy()
    raise pytest.skip("No areaDetector IOC running")


def _prime_ad_plugins(prefix):
    """Enable all plugins and do a single acquire so ArraySize gets populated."""
    import time

    plugins = [
        "image1:", "TIFF1:", "HDF1:", "JPEG1:", "netCDF1:", "Nexus1:",
        "Magick1:", "ROI1:", "ROI2:", "ROI3:", "ROI4:",
        "Stats1:", "Stats2:", "Stats3:", "Stats4:", "Stats5:",
        "Proc1:", "Trans1:", "Over1:", "CC1:", "CC2:", "CB1:",
        "Attr1:", "FFT1:", "Codec1:", "Codec2:", "BadPix1:",
        "Scatter1:", "Gather1:", "Pva1:",
    ]

    # Enable callbacks on all plugins
    enable_sigs = []
    for plug in plugins:
        pv = prefix + plug + "EnableCallbacks"
        try:
            sig = EpicsSignal(pv, name="enable")
            sig.wait_for_connection(timeout=2)
            sig.put(1, wait=True)
            enable_sigs.append(sig)
        except Exception:
            pass

    # Single acquire to push data through the plugin chain
    cam_acquire = EpicsSignal(prefix + "cam1:Acquire", name="acquire")
    cam_acquire.wait_for_connection(timeout=5)
    cam_image_mode = EpicsSignal(prefix + "cam1:ImageMode", name="image_mode")
    cam_image_mode.wait_for_connection(timeout=5)
    cam_image_mode.put(0, wait=True)  # Single mode
    cam_acquire.put(1, wait=True)
    time.sleep(1)  # Wait for data to propagate through plugins

    # Cleanup
    for sig in enable_sigs:
        sig.destroy()
    cam_acquire.destroy()
    cam_image_mode.destroy()
    print("AD plugins primed")


@pytest.fixture(scope="function")
def prefix():
    "Fixed PV prefix — uses the combined caproto IOC"
    return SIGNAL_PREFIX


@pytest.fixture(scope="function")
def fake_motor_ioc(request):
    """Connect to the already-running combined caproto IOC (no subprocess)."""
    name = "Fake motor IOC"
    prefix = MOTOR_PREFIX
    pvs = dict(
        setpoint=f"{prefix}setpoint",
        readback=f"{prefix}readback",
        moving=f"{prefix}moving",
        actuate=f"{prefix}actuate",
        stop=f"{prefix}stop",
        step_size=f"{prefix}step_size",
    )

    # Verify IOC is running
    sig = EpicsSignalRO(pvs["setpoint"], name="check")
    try:
        sig.wait_for_connection(timeout=5)
    except TimeoutError:
        pytest.skip("Combined caproto IOC not running (python caproto_ioc.py)")
    finally:
        sig.destroy()

    return SimpleNamespace(
        process=None, prefix=prefix, name=name, pvs=pvs, type="caproto"
    )


@pytest.fixture(scope="function")
def signal_test_ioc(request):
    """Connect to the already-running combined caproto IOC (no subprocess)."""
    name = "test_signal IOC"
    prefix = SIGNAL_PREFIX
    pvs = dict(
        read_only=f"{prefix}read_only",
        read_write=f"{prefix}read_write",
        pair_set=f"{prefix}pair_set",
        pair_rbv=f"{prefix}pair_rbv",
        waveform=f"{prefix}waveform",
        bool_enum=f"{prefix}bool_enum",
        alarm_status=f"{prefix}alarm_status",
        set_severity=f"{prefix}set_severity",
        path=f"{prefix}path",
    )

    # Verify IOC is running
    sig = EpicsSignalRO(pvs["read_only"], name="check")
    try:
        sig.wait_for_connection(timeout=5)
    except TimeoutError:
        pytest.skip("Combined caproto IOC not running (python caproto_ioc.py)")
    finally:
        sig.destroy()

    return SimpleNamespace(
        process=None, prefix=prefix, name=name, pvs=pvs, type="caproto"
    )


@pytest.fixture(scope="function")
def cleanup(request):
    "Destroy all items added to the list during the finalizer"
    items = []

    class Cleaner:
        def add(self, item):
            items.append(item)

    def clean():
        for item in items:
            print("Destroying", item.name)
            item.destroy()
        items.clear()

    request.addfinalizer(clean)
    return Cleaner()
