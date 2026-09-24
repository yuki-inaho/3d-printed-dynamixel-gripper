import cadquery as cq
import pytest

from gripper_design.pg3 import to_arm
from gripper_design.pg3_crank_representation import build_candidate
from scripts.review_pg3_washer_contacts import controlled_containment


@pytest.fixture(scope="module")
def candidate():
    return build_candidate()


def test_native_material_matches_authoritative_part(candidate):
    donor = cq.importers.importStep("references/pg3-c9/PG3_C92_J28/CAD/parts/07_crank.step").val()
    proof = controlled_containment(donor, candidate, equal=True)
    assert proof["pass"], proof
    assert max(proof["residuals_mm3"]) < 1e-4


@pytest.mark.parametrize("angle", (25, 90, 135))
def test_saved_placed_candidate_obeys_independent_copy_identity(candidate, angle, tmp_path):
    placed = to_arm(candidate.rotate((0, 0, 0), (0, 0, 1), angle))
    path = tmp_path / "crank.step"
    cq.exporters.export(placed, str(path))
    saved = cq.importers.importStep(str(path)).val()
    assert saved.isValid()
    assert len(saved.Solids()) == 1
    assert saved.cut(saved.copy()).Volume() < 1e-4
    assert abs(saved.intersect(saved.copy()).Volume() - saved.Volume()) < 1e-4


def test_source_drift_is_rejected(tmp_path):
    source = tmp_path / "design.py"
    source.write_text("raise RuntimeError('must not execute changed source')\n")
    with pytest.raises(ValueError, match="source SHA"):
        build_candidate(source)


@pytest.mark.parametrize("angle", (25, 90, 135))
def test_installation_entrypoint_uses_working_crank_representation(angle):
    from gripper_design.pg3 import PG3Model
    from gripper_design.pg3_installation import installed_assembly

    host = installed_assembly(PG3Model(), angle)["PG3_crank"]
    proof = controlled_containment(host, host.copy(), equal=True)
    assert proof["pass"], proof
