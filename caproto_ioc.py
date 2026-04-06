#!/usr/bin/env python3
"""
Combined caproto IOC for ophyd tests.

Serves all PVs needed by the caproto-dependent ophyd tests under fixed prefixes:

  - test:motor:   — Fake motor (setpoint, readback, moving, actuate, stop)
  - test:signal:  — Signal test (read_only, read_write, pair_set, waveform, etc.)
  - test:mca:     — MCA + DXP
  - test:scaler:  — Scaler with 32 channels

Usage:
    python caproto_ioc.py
    python caproto_ioc.py -v   # verbose
"""

import numpy as np
from caproto import ChannelType
from caproto.server import (
    PVGroup,
    SubGroup,
    get_pv_pair_wrapper,
    pvproperty,
    run,
)

pvproperty_with_rbv = get_pv_pair_wrapper(setpoint_suffix="", readback_suffix="_RBV")
unknown = int


# ── Fake Motor ────────────────────────────────────────────────────────

class FakeMotorIOC(PVGroup):
    setpoint = pvproperty(value=0.0, precision=1)
    readback = pvproperty(value=0.0, read_only=True, precision=1)
    moving = pvproperty(value=0.0, read_only=True)
    actuate = pvproperty(value=0)
    stop = pvproperty(value=0)
    step_size = pvproperty(value=0.1)

    @actuate.scan(period=0.1)
    async def actuate(self, instance, async_lib):
        step_size = self.step_size.value
        setpoint = self.setpoint.value
        readback = self.readback.value
        moving = self.moving.value
        actuate = self.actuate.value
        stop = self.stop.value

        if stop:
            await self.stop.write(0)
            await self.moving.write(0)
        elif actuate or moving:
            if moving != 1:
                await self.actuate.write(0)
                await self.moving.write(1)

            delta = setpoint - readback
            if abs(delta) <= step_size:
                await self.readback.write(setpoint)
                await self.moving.write(0)
            else:
                await self.readback.write(readback + np.sign(delta) * step_size)


# ── Signal Test ───────────────────────────────────────────────────────

class SignalTestIOC(PVGroup):
    read_only = pvproperty(value=0.0, read_only=True, alarm_group="alarm_a")
    read_write = pvproperty(
        value=0.0,
        lower_ctrl_limit=-100.0,
        upper_ctrl_limit=100.0,
        alarm_group="alarm_a",
    )

    pair_rbv = pvproperty(value=0.0, read_only=True, alarm_group="alarm_a")
    pair_set = pvproperty(
        value=0.0,
        lower_ctrl_limit=-100.0,
        upper_ctrl_limit=100.0,
        alarm_group="alarm_a",
    )

    @pair_set.putter
    async def pair_set(self, instance, value):
        await self.pair_rbv.write(value=value)

    waveform = pvproperty(
        value=[ord("a"), ord("b"), ord("c")], read_only=True, alarm_group="alarm_a"
    )
    bool_enum = pvproperty(value=True, alarm_group="alarm_a")
    alarm_status = pvproperty(value=0)
    set_severity = pvproperty(value=0)

    @set_severity.putter
    async def set_severity(self, instance, severity):
        await self.read_only.alarm.write(
            severity=severity, status=self.alarm_status.value
        )

    INITIAL_PATH = "/path/here"
    path = pvproperty(value=INITIAL_PATH, max_length=255)
    path_RBV = pvproperty(value=INITIAL_PATH, max_length=255)

    @path.putter
    async def path(self, instance, value):
        await self.path_RBV.write(value=value)
        return value


# ── MCA + DXP ─────────────────────────────────────────────────────────

class MCAROIGroup(PVGroup):
    label = pvproperty(value="label", name="NM")
    count = pvproperty(value=1, name="", read_only=True)
    net_count = pvproperty(name="N", dtype=unknown, read_only=True)
    preset_count = pvproperty(name="P", dtype=unknown)
    is_preset = pvproperty(name="IP", dtype=unknown)
    bkgnd_chans = pvproperty(name="BG", dtype=unknown)
    hi_chan = pvproperty(name="HI", dtype=unknown)
    lo_chan = pvproperty(name="LO", dtype=unknown)


class EpicsMCAGroup(PVGroup):
    stop_signal = pvproperty(name="Stop", dtype=unknown)
    preset_real_time = pvproperty(name=".PRTM", dtype=unknown)
    preset_live_time = pvproperty(name=".PLTM", dtype=unknown)
    elapsed_real_time = pvproperty(name=".ERTM", dtype=unknown, read_only=True)
    elapsed_live_time = pvproperty(name=".ELTM", dtype=unknown, read_only=True)
    spectrum = pvproperty(name="", dtype=float, read_only=True)
    background = pvproperty(name=".BG", dtype=unknown, read_only=True)
    mode = pvproperty(value="List", name=".MODE", dtype=str)

    class RoisGroup(PVGroup):
        roi0 = SubGroup(MCAROIGroup, prefix=".R0")
        roi1 = SubGroup(MCAROIGroup, prefix=".R1")
        roi2 = SubGroup(MCAROIGroup, prefix=".R2")
        roi3 = SubGroup(MCAROIGroup, prefix=".R3")
        roi4 = SubGroup(MCAROIGroup, prefix=".R4")
        roi5 = SubGroup(MCAROIGroup, prefix=".R5")
        roi6 = SubGroup(MCAROIGroup, prefix=".R6")
        roi7 = SubGroup(MCAROIGroup, prefix=".R7")
        roi8 = SubGroup(MCAROIGroup, prefix=".R8")
        roi9 = SubGroup(MCAROIGroup, prefix=".R9")
        roi10 = SubGroup(MCAROIGroup, prefix=".R10")
        roi11 = SubGroup(MCAROIGroup, prefix=".R11")
        roi12 = SubGroup(MCAROIGroup, prefix=".R12")
        roi13 = SubGroup(MCAROIGroup, prefix=".R13")
        roi14 = SubGroup(MCAROIGroup, prefix=".R14")
        roi15 = SubGroup(MCAROIGroup, prefix=".R15")
        roi16 = SubGroup(MCAROIGroup, prefix=".R16")
        roi17 = SubGroup(MCAROIGroup, prefix=".R17")
        roi18 = SubGroup(MCAROIGroup, prefix=".R18")
        roi19 = SubGroup(MCAROIGroup, prefix=".R19")
        roi20 = SubGroup(MCAROIGroup, prefix=".R20")
        roi21 = SubGroup(MCAROIGroup, prefix=".R21")
        roi22 = SubGroup(MCAROIGroup, prefix=".R22")
        roi23 = SubGroup(MCAROIGroup, prefix=".R23")
        roi24 = SubGroup(MCAROIGroup, prefix=".R24")
        roi25 = SubGroup(MCAROIGroup, prefix=".R25")
        roi26 = SubGroup(MCAROIGroup, prefix=".R26")
        roi27 = SubGroup(MCAROIGroup, prefix=".R27")
        roi28 = SubGroup(MCAROIGroup, prefix=".R28")
        roi29 = SubGroup(MCAROIGroup, prefix=".R29")
        roi30 = SubGroup(MCAROIGroup, prefix=".R30")
        roi31 = SubGroup(MCAROIGroup, prefix=".R31")

    rois = SubGroup(RoisGroup, prefix="")

    start = pvproperty(name="Start", dtype=unknown)
    erase = pvproperty(name="Erase", dtype=unknown)
    erase_start = pvproperty(name="EraseStart", dtype=unknown)
    check_acquiring = pvproperty(name="CheckACQG", dtype=unknown)
    client_wait = pvproperty(name="ClientWait", dtype=unknown)
    enable_wait = pvproperty(name="EnableWait", dtype=unknown)
    force_read = pvproperty(name="Read", dtype=unknown)
    set_client_wait = pvproperty(name="SetClientWait", dtype=unknown)
    status = pvproperty(name="Status", dtype=unknown)
    when_acq_stops = pvproperty(name="WhenAcqStops", dtype=unknown)
    why1 = pvproperty(name="Why1", dtype=unknown)
    why2 = pvproperty(name="Why2", dtype=unknown)
    why3 = pvproperty(name="Why3", dtype=unknown)
    why4 = pvproperty(name="Why4", dtype=unknown)


class EpicsDXPGroup(PVGroup):
    preset_mode = pvproperty_with_rbv(value="Live time", name="PresetMode", dtype=str)
    live_time_output = pvproperty_with_rbv(
        value="livetimeoutput", name="LiveTimeOutput", dtype=str
    )
    elapsed_live_time = pvproperty(name="ElapsedLiveTime", dtype=unknown)
    elapsed_real_time = pvproperty(name="ElapsedRealTime", dtype=unknown)
    elapsed_trigger_live_time = pvproperty(name="ElapsedTriggerLiveTime", dtype=unknown)
    trigger_peaking_time = pvproperty_with_rbv(name="TriggerPeakingTime", dtype=unknown)
    trigger_threshold = pvproperty_with_rbv(name="TriggerThreshold", dtype=unknown)
    trigger_gap_time = pvproperty_with_rbv(name="TriggerGapTime", dtype=unknown)
    trigger_output = pvproperty_with_rbv(
        value="trigger_output", name="TriggerOutput", dtype=str
    )
    max_width = pvproperty_with_rbv(name="MaxWidth", dtype=unknown)
    peaking_time = pvproperty_with_rbv(name="PeakingTime", dtype=unknown)
    energy_threshold = pvproperty_with_rbv(name="EnergyThreshold", dtype=unknown)
    gap_time = pvproperty_with_rbv(name="GapTime", dtype=unknown)
    baseline_cut_percent = pvproperty_with_rbv(name="BaselineCutPercent", dtype=unknown)
    baseline_cut_enable = pvproperty_with_rbv(name="BaselineCutEnable", dtype=unknown)
    baseline_filter_length = pvproperty_with_rbv(
        name="BaselineFilterLength", dtype=unknown
    )
    baseline_threshold = pvproperty_with_rbv(name="BaselineThreshold", dtype=unknown)
    baseline_energy_array = pvproperty(name="BaselineEnergyArray", dtype=unknown)
    baseline_histogram = pvproperty(name="BaselineHistogram", dtype=unknown)
    preamp_gain = pvproperty_with_rbv(name="PreampGain", dtype=unknown)
    detector_polarity = pvproperty_with_rbv(name="DetectorPolarity", dtype=unknown)
    reset_delay = pvproperty_with_rbv(name="ResetDelay", dtype=unknown)
    decay_time = pvproperty_with_rbv(name="DecayTime", dtype=unknown)
    max_energy = pvproperty_with_rbv(name="MaxEnergy", dtype=unknown)
    adc_percent_rule = pvproperty_with_rbv(name="ADCPercentRule", dtype=unknown)
    triggers = pvproperty(name="Triggers", dtype=unknown, read_only=True)
    events = pvproperty(name="Events", dtype=unknown, read_only=True)
    overflows = pvproperty(name="Overflows", dtype=unknown, read_only=True)
    underflows = pvproperty(name="Underflows", dtype=unknown, read_only=True)
    input_count_rate = pvproperty(name="InputCountRate", dtype=unknown, read_only=True)
    output_count_rate = pvproperty(
        name="OutputCountRate", dtype=unknown, read_only=True
    )
    mca_bin_width = pvproperty(name="MCABinWidth_RBV", dtype=unknown, read_only=True)
    calibration_energy = pvproperty(
        name="CalibrationEnergy_RBV", dtype=unknown, read_only=True
    )
    current_pixel = pvproperty(name="CurrentPixel", dtype=unknown)
    dynamic_range = pvproperty(name="DynamicRange_RBV", dtype=unknown, read_only=True)
    preset_events = pvproperty_with_rbv(name="PresetEvents", dtype=unknown)
    preset_triggers = pvproperty_with_rbv(name="PresetTriggers", dtype=unknown)
    trace_data = pvproperty(name="TraceData", dtype=unknown)
    trace_mode = pvproperty_with_rbv(value="Mode", name="TraceMode", dtype=str)
    trace_time_array = pvproperty(name="TraceTimeArray", dtype=unknown)
    trace_time = pvproperty_with_rbv(name="TraceTime", dtype=unknown)


class McaDxpIOC(PVGroup):
    mca = SubGroup(EpicsMCAGroup, prefix="mca")
    dxp = SubGroup(EpicsDXPGroup, prefix="dxp:")


# ── Scaler ────────────────────────────────────────────────────────────

class EpicsScalerGroup(PVGroup):
    count = pvproperty(name=".CNT", dtype=int)
    count_mode = pvproperty(
        value="OneShot",
        name=".CONT",
        dtype=ChannelType.ENUM,
        enum_strings=["OneShot", "AutoCount"],
    )
    delay = pvproperty(name=".DLY", dtype=float)
    auto_count_delay = pvproperty(name=".DLY1", dtype=float)

    class ChannelsGroup(PVGroup):
        chan1 = pvproperty(value=0, name=".S1", dtype=int, read_only=True)
        chan2 = pvproperty(value=0, name=".S2", dtype=int, read_only=True)
        chan3 = pvproperty(value=0, name=".S3", dtype=int, read_only=True)
        chan4 = pvproperty(value=0, name=".S4", dtype=int, read_only=True)
        chan5 = pvproperty(value=0, name=".S5", dtype=int, read_only=True)
        chan6 = pvproperty(value=0, name=".S6", dtype=int, read_only=True)
        chan7 = pvproperty(value=0, name=".S7", dtype=int, read_only=True)
        chan8 = pvproperty(value=0, name=".S8", dtype=int, read_only=True)
        chan9 = pvproperty(value=0, name=".S9", dtype=int, read_only=True)
        chan10 = pvproperty(value=0, name=".S10", dtype=int, read_only=True)
        chan11 = pvproperty(value=0, name=".S11", dtype=int, read_only=True)
        chan12 = pvproperty(value=0, name=".S12", dtype=int, read_only=True)
        chan13 = pvproperty(value=0, name=".S13", dtype=int, read_only=True)
        chan14 = pvproperty(value=0, name=".S14", dtype=int, read_only=True)
        chan15 = pvproperty(value=0, name=".S15", dtype=int, read_only=True)
        chan16 = pvproperty(value=0, name=".S16", dtype=int, read_only=True)
        chan17 = pvproperty(value=0, name=".S17", dtype=int, read_only=True)
        chan18 = pvproperty(value=0, name=".S18", dtype=int, read_only=True)
        chan19 = pvproperty(value=0, name=".S19", dtype=int, read_only=True)
        chan20 = pvproperty(value=0, name=".S20", dtype=int, read_only=True)
        chan21 = pvproperty(value=0, name=".S21", dtype=int, read_only=True)
        chan22 = pvproperty(value=0, name=".S22", dtype=int, read_only=True)
        chan23 = pvproperty(value=0, name=".S23", dtype=int, read_only=True)
        chan24 = pvproperty(value=0, name=".S24", dtype=int, read_only=True)
        chan25 = pvproperty(value=0, name=".S25", dtype=int, read_only=True)
        chan26 = pvproperty(value=0, name=".S26", dtype=int, read_only=True)
        chan27 = pvproperty(value=0, name=".S27", dtype=int, read_only=True)
        chan28 = pvproperty(value=0, name=".S28", dtype=int, read_only=True)
        chan29 = pvproperty(value=0, name=".S29", dtype=int, read_only=True)
        chan30 = pvproperty(value=0, name=".S30", dtype=int, read_only=True)
        chan31 = pvproperty(value=0, name=".S31", dtype=int, read_only=True)
        chan32 = pvproperty(value=0, name=".S32", dtype=int, read_only=True)

    channels = SubGroup(ChannelsGroup, prefix="")

    class NamesGroup(PVGroup):
        name1 = pvproperty(value="name", name=".NM1", dtype=ChannelType.STRING)
        name2 = pvproperty(value="name", name=".NM2", dtype=ChannelType.STRING)
        name3 = pvproperty(value="name", name=".NM3", dtype=ChannelType.STRING)
        name4 = pvproperty(value="name", name=".NM4", dtype=ChannelType.STRING)
        name5 = pvproperty(value="name", name=".NM5", dtype=ChannelType.STRING)
        name6 = pvproperty(value="name", name=".NM6", dtype=ChannelType.STRING)
        name7 = pvproperty(value="name", name=".NM7", dtype=ChannelType.STRING)
        name8 = pvproperty(value="name", name=".NM8", dtype=ChannelType.STRING)
        name9 = pvproperty(value="name", name=".NM9", dtype=ChannelType.STRING)
        name10 = pvproperty(value="name", name=".NM10", dtype=ChannelType.STRING)
        name11 = pvproperty(value="name", name=".NM11", dtype=ChannelType.STRING)
        name12 = pvproperty(value="name", name=".NM12", dtype=ChannelType.STRING)
        name13 = pvproperty(value="name", name=".NM13", dtype=ChannelType.STRING)
        name14 = pvproperty(value="name", name=".NM14", dtype=ChannelType.STRING)
        name15 = pvproperty(value="name", name=".NM15", dtype=ChannelType.STRING)
        name16 = pvproperty(value="name", name=".NM16", dtype=ChannelType.STRING)
        name17 = pvproperty(value="name", name=".NM17", dtype=ChannelType.STRING)
        name18 = pvproperty(value="name", name=".NM18", dtype=ChannelType.STRING)
        name19 = pvproperty(value="name", name=".NM19", dtype=ChannelType.STRING)
        name20 = pvproperty(value="name", name=".NM20", dtype=ChannelType.STRING)
        name21 = pvproperty(value="name", name=".NM21", dtype=ChannelType.STRING)
        name22 = pvproperty(value="name", name=".NM22", dtype=ChannelType.STRING)
        name23 = pvproperty(value="name", name=".NM23", dtype=ChannelType.STRING)
        name24 = pvproperty(value="name", name=".NM24", dtype=ChannelType.STRING)
        name25 = pvproperty(value="name", name=".NM25", dtype=ChannelType.STRING)
        name26 = pvproperty(value="name", name=".NM26", dtype=ChannelType.STRING)
        name27 = pvproperty(value="name", name=".NM27", dtype=ChannelType.STRING)
        name28 = pvproperty(value="name", name=".NM28", dtype=ChannelType.STRING)
        name29 = pvproperty(value="name", name=".NM29", dtype=ChannelType.STRING)
        name30 = pvproperty(value="name", name=".NM30", dtype=ChannelType.STRING)
        name31 = pvproperty(value="name", name=".NM31", dtype=ChannelType.STRING)
        name32 = pvproperty(value="name", name=".NM32", dtype=ChannelType.STRING)

    names = SubGroup(NamesGroup, prefix="")

    time = pvproperty(name=".T", dtype=float)
    freq = pvproperty(name=".FREQ", dtype=float)
    preset_time = pvproperty(name=".TP", dtype=float)
    auto_count_time = pvproperty(name=".TP1", dtype=float)

    class PresetsGroup(PVGroup):
        preset1 = pvproperty(name=".PR1", dtype=int)
        preset2 = pvproperty(name=".PR2", dtype=int)
        preset3 = pvproperty(name=".PR3", dtype=int)
        preset4 = pvproperty(name=".PR4", dtype=int)
        preset5 = pvproperty(name=".PR5", dtype=int)
        preset6 = pvproperty(name=".PR6", dtype=int)
        preset7 = pvproperty(name=".PR7", dtype=int)
        preset8 = pvproperty(name=".PR8", dtype=int)
        preset9 = pvproperty(name=".PR9", dtype=int)
        preset10 = pvproperty(name=".PR10", dtype=int)
        preset11 = pvproperty(name=".PR11", dtype=int)
        preset12 = pvproperty(name=".PR12", dtype=int)
        preset13 = pvproperty(name=".PR13", dtype=int)
        preset14 = pvproperty(name=".PR14", dtype=int)
        preset15 = pvproperty(name=".PR15", dtype=int)
        preset16 = pvproperty(name=".PR16", dtype=int)
        preset17 = pvproperty(name=".PR17", dtype=int)
        preset18 = pvproperty(name=".PR18", dtype=int)
        preset19 = pvproperty(name=".PR19", dtype=int)
        preset20 = pvproperty(name=".PR20", dtype=int)
        preset21 = pvproperty(name=".PR21", dtype=int)
        preset22 = pvproperty(name=".PR22", dtype=int)
        preset23 = pvproperty(name=".PR23", dtype=int)
        preset24 = pvproperty(name=".PR24", dtype=int)
        preset25 = pvproperty(name=".PR25", dtype=int)
        preset26 = pvproperty(name=".PR26", dtype=int)
        preset27 = pvproperty(name=".PR27", dtype=int)
        preset28 = pvproperty(name=".PR28", dtype=int)
        preset29 = pvproperty(name=".PR29", dtype=int)
        preset30 = pvproperty(name=".PR30", dtype=int)
        preset31 = pvproperty(name=".PR31", dtype=int)
        preset32 = pvproperty(name=".PR32", dtype=int)

    presets = SubGroup(PresetsGroup, prefix="")

    class GatesGroup(PVGroup):
        gate1 = pvproperty(name=".G1", dtype=int)
        gate2 = pvproperty(name=".G2", dtype=int)
        gate3 = pvproperty(name=".G3", dtype=int)
        gate4 = pvproperty(name=".G4", dtype=int)
        gate5 = pvproperty(name=".G5", dtype=int)
        gate6 = pvproperty(name=".G6", dtype=int)
        gate7 = pvproperty(name=".G7", dtype=int)
        gate8 = pvproperty(name=".G8", dtype=int)
        gate9 = pvproperty(name=".G9", dtype=int)
        gate10 = pvproperty(name=".G10", dtype=int)
        gate11 = pvproperty(name=".G11", dtype=int)
        gate12 = pvproperty(name=".G12", dtype=int)
        gate13 = pvproperty(name=".G13", dtype=int)
        gate14 = pvproperty(name=".G14", dtype=int)
        gate15 = pvproperty(name=".G15", dtype=int)
        gate16 = pvproperty(name=".G16", dtype=int)
        gate17 = pvproperty(name=".G17", dtype=int)
        gate18 = pvproperty(name=".G18", dtype=int)
        gate19 = pvproperty(name=".G19", dtype=int)
        gate20 = pvproperty(name=".G20", dtype=int)
        gate21 = pvproperty(name=".G21", dtype=int)
        gate22 = pvproperty(name=".G22", dtype=int)
        gate23 = pvproperty(name=".G23", dtype=int)
        gate24 = pvproperty(name=".G24", dtype=int)
        gate25 = pvproperty(name=".G25", dtype=int)
        gate26 = pvproperty(name=".G26", dtype=int)
        gate27 = pvproperty(name=".G27", dtype=int)
        gate28 = pvproperty(name=".G28", dtype=int)
        gate29 = pvproperty(name=".G29", dtype=int)
        gate30 = pvproperty(name=".G30", dtype=int)
        gate31 = pvproperty(name=".G31", dtype=int)
        gate32 = pvproperty(name=".G32", dtype=int)

    gates = SubGroup(GatesGroup, prefix="")

    update_rate = pvproperty(name=".RATE", dtype=int)
    auto_count_update_rate = pvproperty(name=".RAT1", dtype=int)
    egu = pvproperty(value="EGU", name=".EGU", dtype=ChannelType.STRING)


# ── Combined IOC ──────────────────────────────────────────────────────

class CombinedTestIOC(PVGroup):
    motor = SubGroup(FakeMotorIOC, prefix="test:motor:")
    signal = SubGroup(SignalTestIOC, prefix="test:signal:")
    mca = SubGroup(McaDxpIOC, prefix="test:mca:")
    scaler = SubGroup(EpicsScalerGroup, prefix="test:scaler:")


if __name__ == "__main__":
    ioc = CombinedTestIOC(prefix="")
    pvdb = ioc.pvdb

    print(f"Serving {len(pvdb)} PVs:")
    print(f"  test:motor:*   — Fake motor")
    print(f"  test:signal:*  — Signal test")
    print(f"  test:mca:*     — MCA + DXP")
    print(f"  test:scaler:*  — Scaler")
    print()

    import sys
    verbose = "-v" in sys.argv
    run(pvdb, log_pv_names=verbose)
