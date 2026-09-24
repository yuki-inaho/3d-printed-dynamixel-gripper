import cadquery as cq
import pytest

from gripper_design.serviceability import (
    FastenerStack,
    ToolApproach,
    check_counterhold,
    check_fastener_stack,
    check_head_clearance,
    check_tool_access,
)


def test_long_screw_bottoms_out():
    result = check_fastener_stack(
        FastenerStack(
            screw_length_mm=10,
            grip_mm=3,
            available_thread_depth_mm=5,
            minimum_engagement_mm=2,
            tip_clearance_mm=0.5,
        )
    )
    assert result.status == "FAIL"
    assert result.reason_id == "bottoms_out"


def test_short_screw_has_insufficient_engagement():
    result = check_fastener_stack(
        FastenerStack(
            screw_length_mm=4,
            grip_mm=3,
            available_thread_depth_mm=5,
            minimum_engagement_mm=2,
            tip_clearance_mm=0.5,
        )
    )
    assert result.status == "FAIL"
    assert result.reason_id == "insufficient_engagement"


def test_nominal_but_unpurchased_fastener_remains_unknown():
    result = check_fastener_stack(
        FastenerStack(
            screw_length_mm=7,
            grip_mm=3,
            available_thread_depth_mm=5,
            minimum_engagement_mm=2,
            tip_clearance_mm=0.5,
            dimensions_confirmed=False,
        )
    )
    assert result.status == "UNKNOWN"
    assert result.reason_id == "fastener_dimensions_unconfirmed"


def test_fastener_head_collision_is_separate_from_hole_alignment():
    head = cq.Solid.makeCylinder(3, 2, (-0.0, 0.0, 0.0), (0, 0, 1))
    obstacle = cq.Workplane("XY", origin=(0, 0, 1)).box(8, 8, 1).val()
    result = check_head_clearance(head, {"camera_body": obstacle})
    assert result.status == "FAIL"
    assert result.reason_id == "head_collision"


def test_tool_handle_collision_detected_when_shaft_is_clear():
    approach = ToolApproach(
        tip=(0, 0, 0),
        axis=(0, 0, 1),
        shaft_radius_mm=1.5,
        shaft_length_mm=30,
        handle_radius_mm=8,
        handle_length_mm=20,
    )
    obstacle = cq.Workplane("XY", origin=(6, 0, 40)).box(4, 4, 4).val()
    result = check_tool_access(approach, {"link": obstacle}, stage="installed")
    assert result.status == "FAIL"
    assert result.reason_id == "tool_handle_collision"


def test_counterhold_required_but_unavailable_fails():
    result = check_counterhold(required=True, primary_access=True, opposite_access=False)
    assert result.status == "FAIL"
    assert result.reason_id == "counterhold_unavailable"


def test_bench_preassembly_can_pass_while_installed_service_fails():
    approach = ToolApproach(
        tip=(0, 0, 0),
        axis=(0, 0, 1),
        shaft_radius_mm=1.5,
        shaft_length_mm=30,
        handle_radius_mm=8,
        handle_length_mm=20,
    )
    installed_link = cq.Workplane("XY", origin=(6, 0, 40)).box(4, 4, 4).val()
    bench = check_tool_access(approach, {}, stage="bench_preassembly")
    installed = check_tool_access(approach, {"link": installed_link}, stage="installed")
    assert bench.status == "PASS"
    assert installed.status == "FAIL"
    assert bench.metrics["stage"] == "bench_preassembly"
    assert installed.metrics["stage"] == "installed"


def test_l_key_motion_is_not_approximated_as_straight_tool():
    approach = ToolApproach(
        tip=(0, 0, 0),
        axis=(0, 0, 1),
        shaft_radius_mm=1.5,
        shaft_length_mm=30,
        handle_radius_mm=8,
        handle_length_mm=20,
        motion_model="L_key_sweep",
    )
    result = check_tool_access(approach, {}, stage="installed")
    assert result.status == "UNKNOWN"
    assert result.reason_id == "unsupported_tool_motion"


def test_insertion_without_complete_thread_profile_cannot_pass():
    result = check_fastener_stack(FastenerStack(5, 2.35, 4, 1, 0.5))
    assert result.status == "UNKNOWN"
    assert result.reason_id == "full_form_dimensions_unconfirmed"


def full_form_stack(**changes):
    values = {
        "screw_length_mm": 5,
        "grip_mm": 2.35,
        "available_thread_depth_mm": 4,
        "minimum_engagement_mm": 1,
        "tip_clearance_mm": 0.5,
        "screw_tip_lead_mm": 0,
        "receiver_entry_relief_mm": 0.2,
        "unthreaded_reach_into_receiver_mm": 0,
        "receiver_bottom_relief_mm": 0,
    }
    return FastenerStack(**(values | changes))


@pytest.mark.parametrize("lead_turns", [2, 2.5])
def test_tapered_tip_is_not_counted_as_full_form_engagement(lead_turns):
    lead = (25.4 / 28) * lead_turns
    result = check_fastener_stack(full_form_stack(screw_tip_lead_mm=lead))
    assert result.status == "FAIL"
    assert result.reason_id == "insufficient_full_form_engagement"
    assert result.metrics["full_form_engagement_mm"] == pytest.approx(2.45 - lead)


def test_entry_neck_and_bottom_reliefs_are_intersected_not_double_subtracted():
    result = check_fastener_stack(
        full_form_stack(
            unthreaded_reach_into_receiver_mm=0.5,
            receiver_bottom_relief_mm=2,
            screw_tip_lead_mm=0.2,
        )
    )
    assert result.status == "PASS"
    assert result.metrics["full_form_engagement_mm"] == pytest.approx(1.5)


@pytest.mark.parametrize("field", ["screw_length_mm", "screw_tip_lead_mm", "minimum_engagement_mm"])
def test_nonfinite_fastener_dimensions_cannot_pass(field):
    assert check_fastener_stack(full_form_stack(**{field: float("nan")})).status == "ERROR"
