"""Generate synthetic evidence in tmp; never require an ignored historical run."""

import os

import pytest

# Must precede importing MuJoCo: setting this after import does not select EGL.
os.environ.setdefault("MUJOCO_GL", "egl")


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
