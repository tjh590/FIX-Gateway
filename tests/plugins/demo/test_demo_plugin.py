import time
import math
import pytest

from fixgw import cfg
import fixgw.plugins.demo
import fixgw.database as database


def _start_demo_plugin(config_yaml: str):
    conf, conf_meta = cfg.from_yaml(config_yaml, metadata=True)
    pl = fixgw.plugins.demo.Plugin("demo", conf, conf_meta)
    pl.start()
    # Give thread a moment to write initial values
    time.sleep(0.1)
    return pl


def _stop_demo_plugin(pl):
    try:
        pl.stop()
    except Exception:
        pass


def test_demo_tick_rate(database):
    # Use a clear tick rate and short periods to settle quickly
    yaml_cfg = """
tick_rate_hz: 25
engine_sim:
  rpm_mean: 2400.0
  rpm_amp: 200.0
  rpm_period: 1.0
"""
    pl = _start_demo_plugin(yaml_cfg)
    try:
        # Wait for enough samples on a key updated each tick
        key = "TACH1"
        deadline = time.time() + 3.0
        while time.time() < deadline:
            stats = database.get_rate_stats(key)
            if stats and stats.get("samples", 0) >= 15:
                break
            time.sleep(0.05)
        stats = database.get_rate_stats(key)
        assert stats is not None, "No rate stats produced for TACH1"
        avg = stats["avg"]
        # Allow ±20% tolerance for scheduler jitter
        assert 20.0 <= avg <= 30.0, f"avg Hz {avg} not near 25 Hz"
        # Writer should be the plugin name
        assert stats.get("last_writer") == "demo"
    finally:
        _stop_demo_plugin(pl)


def test_demo_fuel_drain_rates(database):
    # Amplify drain rate to observe measurable change quickly
    yaml_cfg = """
tick_rate_hz: 20
fuel_drain:
  enabled: true
  tanks: [FUELQ1, FUELQ2, FUELQ3]
  weights: [0.5, 0.3, 0.2]
  rate_gph: 360.0
"""
    pl = _start_demo_plugin(yaml_cfg)
    try:
        tanks = ["FUELQ1", "FUELQ2", "FUELQ3"]
        # Capture start values
        start_vals = {t: database.read(t)[0] for t in tanks}
        # Measure over a fixed interval
        t0 = time.time()
        time.sleep(1.5)
        t1 = time.time()
        elapsed = t1 - t0
        end_vals = {t: database.read(t)[0] for t in tanks}

        total_drain = (360.0 / 3600.0) * elapsed  # gallons
        expected = {
            "FUELQ1": 0.5 * total_drain,
            "FUELQ2": 0.3 * total_drain,
            "FUELQ3": 0.2 * total_drain,
        }
        # Allow slack for timing and concurrent demo script updates
        for t in tanks:
            actual = start_vals[t] - end_vals[t]
            assert actual > 0.0, f"{t} did not drain"
            assert math.isfinite(actual)
            # 30 mL tolerance (~0.03 gal) for jitter
            assert abs(actual - expected[t]) <= 0.03, (
                f"{t} drain {actual:.3f} != expected {expected[t]:.3f}"
            )
    finally:
        _stop_demo_plugin(pl)


def test_demo_engine_ramps(database):
    # Speed up periods and increase response to observe variation quickly
    yaml_cfg = """
tick_rate_hz: 20
engine_sim:
  rpm_mean: 2450.0
  rpm_amp: 200.0
  rpm_period: 1.0
  map_base: 18.0
  map_amp: 6.0
  map_period: 1.0
  map_rpm_coeff: 0.004
  oilp_base: 55.0
  oilp_amp: 8.0
  oilp_period: 1.0
  oilp_rpm_coeff: 0.003
  fuelf_base: 7.5
  fuelf_amp: 1.5
  fuelf_period: 1.0
  fuelf_rpm_coeff: 0.0015
  oilt_base: 85.0
  oilt_rpm_coeff: 0.02
  oilt_sin_amp: 5.0
  oilt_sin_period: 2.0
  oilt_alpha: 0.2
  egt_base: 650.0
  egt_amp: 40.0
  egt_period: 1.0
  cht_base: 200.0
  cht_amp: 20.0
  cht_period: 1.5
  cht_oilt_coeff: 0.05
  cht_alpha: 0.2
"""
    pl = _start_demo_plugin(yaml_cfg)
    try:
        keys = [
            "OILP1",
            "OILT1",
            "EGT11", "EGT12",
            "CHT11", "CHT12",
        ]
        series = {k: [] for k in keys}
        # Warm-up to allow initial keylist defaults to be overwritten by engine sim
        time.sleep(0.3)
        t_end = time.time() + 2.5
        while time.time() < t_end:
            for k in keys:
                v = database.read(k)[0]
                series[k].append(float(v))
            time.sleep(0.05)

        # 1) Variation exists (not flat)
        assert max(series["OILP1"]) - min(series["OILP1"]) > 1.0
        assert max(series["OILT1"]) - min(series["OILT1"]) > 0.5
        assert max(series["EGT11"]) - min(series["EGT11"]) > 5.0
        assert max(series["CHT11"]) - min(series["CHT11"]) > 2.0

        # 2) Reasonable bounds (no wild excursions) on the most recent samples
        def last_window(vals, n=20):
            return vals[-n:] if len(vals) >= n else vals

        for v in last_window(series["OILP1"]):
            assert 45.0 <= v <= 65.0
        for v in last_window(series["OILT1"]):
            assert 70.0 <= v <= 100.0
        for v in last_window(series["EGT11"]):
            assert 590.0 <= v <= 710.0
        for v in last_window(series["CHT11"]):
            assert 170.0 <= v <= 230.0

        # 3) Different cylinders are not identical (phase offsets)
        def rms_diff(a, b):
            n = min(len(a), len(b))
            if n == 0:
                return 0.0
            s = 0.0
            for i in range(n):
                d = a[i] - b[i]
                s += d * d
            return math.sqrt(s / n)

        assert rms_diff(series["EGT11"], series["EGT12"]) > 1.0
        assert rms_diff(series["CHT11"], series["CHT12"]) > 0.5
    finally:
        _stop_demo_plugin(pl)
