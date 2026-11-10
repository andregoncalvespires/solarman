from conftest import pv_monitor

M = pv_monitor.PVBalanceMonitor
MIN = 60.0


def run(mon, samples, start=1_000_000.0, step=30.0, elevation=40.0, connected=True, readings=None):
    """Feed `samples` (list of power dicts), one per `step` seconds."""
    t = start
    for powers in samples:
        mon.update(t, powers, elevation, connected, readings)
        t += step
    return t


HEALTHY = {1: 250.0, 2: 260.0, 3: 255.0, 4: 248.0}
DEAD3 = {1: 250.0, 2: 260.0, 3: 0.0, 4: 248.0}


def test_dead_module_flagged_after_on_time_only():
    mon = M([1, 2, 3, 4], on_seconds=1800)
    run(mon, [DEAD3] * 59)                       # 58 steps * 30 s = 1740 s counted
    assert not mon.has_problem
    run(mon, [DEAD3] * 5, start=1_000_000.0 + 59 * 30)
    assert mon.problem_modules == [3]


def test_healthy_never_flagged():
    mon = M([1, 2, 3, 4])
    run(mon, [HEALTHY] * 500)
    assert not mon.has_problem


def test_clouds_hit_all_modules_alike():
    mon = M([1, 2, 3, 4], min_power=50)
    run(mon, [{n: p * 0.2 for n, p in HEALTHY.items()}] * 500)   # ~50 W each, still balanced
    assert not mon.has_problem


def test_low_reference_pauses_evaluation():
    mon = M([1, 2, 3, 4], min_power=50)
    run(mon, [{1: 20.0, 2: 22.0, 3: 0.0, 4: 21.0}] * 500)        # too dark to judge
    assert not mon.has_problem
    assert mon.ratios[3] is None


def test_low_sun_or_disconnected_pause_the_clock():
    mon = M([1, 2, 3, 4], on_seconds=600)
    run(mon, [DEAD3] * 100, elevation=5.0)
    run(mon, [DEAD3] * 100, connected=False)
    assert not mon.has_problem


def test_night_does_not_reset_or_clear():
    mon = M([1, 2, 3, 4], on_seconds=600)
    t = run(mon, [DEAD3] * 30)
    assert mon.problem_modules == [3]
    run(mon, [{}] * 1000, start=t, connected=False)              # the whole night
    assert mon.problem_modules == [3]


def test_recovery_needs_off_time_and_hysteresis():
    mon = M([1, 2, 3, 4], on_seconds=600, off_seconds=300)
    t = run(mon, [DEAD3] * 30)
    assert mon.has_problem
    partial = {1: 250.0, 2: 260.0, 3: 150.0, 4: 248.0}           # 60 %: above 50 %, below recovery 70 %
    t = run(mon, [partial] * 40, start=t)
    assert mon.has_problem
    run(mon, [HEALTHY] * 20, start=t)
    assert not mon.has_problem
    assert mon.since == {}


def test_short_shading_does_not_trigger():
    mon = M([1, 2, 3, 4], on_seconds=1800)
    t = run(mon, [DEAD3] * 20)                                    # 10 min shaded
    run(mon, [HEALTHY] * 100, start=t)
    assert not mon.has_problem


def test_two_dead_modules_both_flagged():
    mon = M([1, 2, 3, 4], on_seconds=600)
    run(mon, [{1: 250.0, 2: 260.0, 3: 0.0, 4: 0.0}] * 40)
    assert mon.problem_modules == [3, 4]


def test_hints():
    mon = M([1, 2, 3, 4], on_seconds=600)
    run(mon, [DEAD3] * 40, readings={3: (0.0, 0.0)})
    assert mon.hints[3] == pv_monitor.HINT_OPEN_CIRCUIT
    mon = M([1, 2, 3, 4], on_seconds=600)
    run(mon, [DEAD3] * 40, readings={3: (38.0, 0.0)})
    assert mon.hints[3] == pv_monitor.HINT_NO_CURRENT


def test_requires_three_inputs():
    mon = M([1, 2])
    assert not mon.enabled
    run(mon, [{1: 250.0, 2: 0.0}] * 500)
    assert not mon.has_problem


def test_restore_keeps_problem_until_healthy():
    mon = M([1, 2, 3, 4], off_seconds=300)
    mon.restore([3], {3: 123.0})
    assert mon.problem_modules == [3] and mon.since == {3: 123.0}
    run(mon, [HEALTHY] * 20)
    assert not mon.has_problem


def test_gap_longer_than_cap_is_not_counted():
    mon = M([1, 2, 3, 4], on_seconds=1800)
    mon.update(0.0, DEAD3, 40.0, True)
    mon.update(100000.0, DEAD3, 40.0, True)                       # huge gap counts at most MAX_STEP
    assert not mon.has_problem
