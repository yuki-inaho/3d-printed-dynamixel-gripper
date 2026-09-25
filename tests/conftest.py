"""Generate synthetic evidence in tmp; never require an ignored historical run."""

import os

import pytest

# Must precede importing MuJoCo: setting this after import does not select EGL.
os.environ.setdefault("MUJOCO_GL", "egl")


def pytest_configure(config):
    """Serve repeated STEP parses from a content-addressed cache in .pytest_cache.

    See scripts.step_cache.read_rows: keyed by file SHA-256 and kernel versions,
    so edited inputs are re-parsed. Set CAD_STEP_CACHE_DIR= (empty) to disable.
    """
    cache = getattr(config, "cache", None)
    if cache is not None and "CAD_STEP_CACHE_DIR" not in os.environ:
        os.environ["CAD_STEP_CACHE_DIR"] = str(cache.mkdir("step-brep"))


# Parallel scheduling for `pytest -n N --dist loadgroup` (README). Each module is
# one group, so module fixtures still run once; the heaviest modules (measured
# with --durations, after the STEP cache made their fixtures cheap) are split into
# a few chunks so one worker does not carry a whole 2-minute file; the modules
# using the synthetic calibration run share a group so it is rendered once.
# Heavy groups are queued first. Sequential runs are untouched.
_CHUNKS = {
    "test_pg3_guide_relief": 5,
    "test_pg3_pivot_motion": 3,
    "test_pg3_crank_representation": 3,
    "test_pg3_bench_cluster": 2,
    "test_pg3": 2,
}
_SYNTHETIC_RUN_MODULES = frozenset(
    {"test_calibrate", "test_calibration_demo", "test_detect_aprilgrid", "test_mujoco_calibration"}
)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    if "PYTEST_XDIST_WORKER" not in os.environ:
        return
    priority = {name: rank for rank, name in enumerate([*_CHUNKS, "synthetic_run"])}
    seen = {}
    keyed = []
    for position, item in enumerate(items):
        module = item.module.__name__.rsplit(".", 1)[-1]
        index = seen[module] = seen.get(module, -1) + 1
        if module in _SYNTHETIC_RUN_MODULES:
            family, group = "synthetic_run", "synthetic_run"
        elif module in _CHUNKS:
            family, group = module, f"{module}#{index % _CHUNKS[module]}"
        else:
            family, group = module, module
        if not item.get_closest_marker("xdist_group"):
            item.add_marker(pytest.mark.xdist_group(group))
        keyed.append((priority.get(family, len(priority)), position, item))
    items[:] = [item for *_, item in sorted(keyed, key=lambda k: k[:2])]


@pytest.fixture(scope="session")
def synthetic_run(tmp_path_factory):
    from scripts.run_calibration_demo import run_demo

    output = tmp_path_factory.mktemp("synthetic") / "run"
    run_demo("specs/simulation_calibration.yaml", output)
    return output


@pytest.fixture(scope="session")
def render_run(synthetic_run):
    return synthetic_run / "rendered"


@pytest.fixture(scope="session")
def calibration_inputs(synthetic_run):
    return (
        synthetic_run / "detections/detections.json",
        synthetic_run / "rendered/ground_truth.json",
    )
