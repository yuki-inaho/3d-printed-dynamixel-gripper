import cadquery as cq

from scripts.review_pg3_components import inspect_components


def test_all_component_pairs_cover_hidden_penetration_and_clearance():
    a = cq.Compound.makeCompound(
        [
            cq.Solid.makeBox(2, 2, 2),
            cq.Solid.makeBox(2, 2, 2, (10, 0, 0)),
        ]
    )
    clear = cq.Solid.makeBox(1, 1, 1, (5, 0, 0))
    hit = clear.translate((5, 0, 0))
    assert inspect_components(a, clear)["status"] == "PASS"
    result = inspect_components(a, hit)
    assert result["status"] == "FAIL"
    assert result["component_counts"] == [2, 1]
    assert len(result["checks"]["pairs"]) == 2


def test_mixed_surface_obstacle_is_not_silently_dropped():
    solid = cq.Solid.makeBox(2, 2, 2)
    mixed = cq.Compound.makeCompound([solid, solid.translate((5, 0, 0)).Faces()[0]])
    assert inspect_components(mixed, solid)["status"] == "UNKNOWN"


def test_per_component_tolerance_does_not_multiply_allowance(monkeypatch):
    import scripts.review_pg3_components as module

    def small_intersections(shapes, pairs):
        return {"pairs": [{"status": "PASS", "volume_mm3": 0.00006} for _ in pairs]}

    monkeypatch.setattr(module, "inspect_pairs", small_intersections)
    one = cq.Solid.makeBox(1, 1, 1)
    two = cq.Compound.makeCompound([one, one.translate((2, 0, 0))])
    assert inspect_components(two, one)["status"] == "UNKNOWN"
