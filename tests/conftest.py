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
