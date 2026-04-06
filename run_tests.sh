#!/bin/bash
# Run ophyd tests grouped to avoid caproto IOC / CA search contention.
#
# Usage:
#   ./run_tests.sh              # Run all groups sequentially
#   ./run_tests.sh pure         # Only pure-logic tests (no IOC needed)
#   ./run_tests.sh motorsim     # Only motorsim-marked tests (ophyd-test-ioc needed)
#   ./run_tests.sh adsim        # Only adsim-marked tests (ophyd-test-ioc needed)
#   ./run_tests.sh caproto      # Only caproto IOC tests (caproto_ioc.py needed)

set -e

PYTHON="${PYTHON:-/Users/stevek/mamba/envs/bs2026.1/bin/python}"
PYTEST="$PYTHON -m pytest"
ROOT="$(cd "$(dirname "$0")" && pwd)"
COMMON_ARGS="-vv --tb=short"

# Tests that need no IOC at all
PURE_TESTS=(
    ophyd_tests/test_device.py
    ophyd_tests/test_hints.py
    ophyd_tests/test_kind.py
    ophyd_tests/test_log.py
    ophyd_tests/test_main.py
    ophyd_tests/test_ophydobj.py
    ophyd_tests/test_positioner.py
    ophyd_tests/test_quadem.py
    ophyd_tests/test_sim.py
    ophyd_tests/test_status.py
    ophyd_tests/test_units.py
    ophyd_tests/test_utils.py
    ophyd_tests/test_versioning.py
    ophyd_tests/test_docs.py
)

# Tests that require the ophyd-test-ioc (motorsim marker)
MOTORSIM_TESTS=(
    ophyd_tests/test_epicsmotor.py
    ophyd_tests/test_pseudopos.py
    ophyd_tests/test_signalpositioner.py
    ophyd_tests/test_timestamps.py
    "ophyd_tests/test_flyers.py -m motorsim"
    "ophyd_tests/test_pvpositioner.py -m motorsim"
    "ophyd_tests/test_signal.py -m motorsim"
)

# Tests that require the ophyd-test-ioc (adsim marker)
ADSIM_TESTS=(
    "ophyd_tests/test_areadetector.py -m adsim"
    "ophyd_tests/test_flyers.py -m adsim"
)

# Tests that use the combined caproto IOC (python caproto_ioc.py)
CAPROTO_TESTS=(
    "ophyd_tests/test_signal.py -m 'not motorsim' -k 'not pv_reuse'"
    "ophyd_tests/test_pvpositioner.py -m 'not motorsim'"
    ophyd_tests/test_mca.py
    ophyd_tests/test_scaler.py
)


run_group() {
    local group_name="$1"
    shift
    local tests=("$@")

    echo ""
    echo "========================================"
    echo "  Group: $group_name"
    echo "========================================"

    local pass=0 fail=0
    for test_spec in "${tests[@]}"; do
        echo ""
        echo "--- $test_spec ---"
        if eval "$PYTEST $COMMON_ARGS $test_spec"; then
            ((pass++))
        else
            ((fail++))
        fi
    done

    echo ""
    echo "[$group_name] $pass passed, $fail failed (out of ${#tests[@]} test specs)"
    return $fail
}

cd "$ROOT"

total_fail=0

case "${1:-all}" in
    pure)
        run_group "Pure (no IOC)" "${PURE_TESTS[@]}" || ((total_fail++))
        ;;
    motorsim)
        run_group "Motorsim (ophyd-test-ioc)" "${MOTORSIM_TESTS[@]}" || ((total_fail++))
        ;;
    adsim)
        run_group "ADsim (ophyd-test-ioc)" "${ADSIM_TESTS[@]}" || ((total_fail++))
        ;;
    caproto)
        run_group "Caproto IOC (caproto_ioc.py)" "${CAPROTO_TESTS[@]}" || ((total_fail++))
        ;;
    all)
        run_group "Pure (no IOC)" "${PURE_TESTS[@]}" || ((total_fail++))
        run_group "Motorsim (ophyd-test-ioc)" "${MOTORSIM_TESTS[@]}" || ((total_fail++))
        run_group "ADsim (ophyd-test-ioc)" "${ADSIM_TESTS[@]}" || ((total_fail++))
        run_group "Caproto IOC (caproto_ioc.py)" "${CAPROTO_TESTS[@]}" || ((total_fail++))
        ;;
    *)
        echo "Usage: $0 {all|pure|motorsim|adsim|caproto}"
        exit 1
        ;;
esac

echo ""
echo "========================================"
if [ $total_fail -eq 0 ]; then
    echo "  All groups passed!"
else
    echo "  $total_fail group(s) had failures"
fi
echo "========================================"
exit $total_fail
