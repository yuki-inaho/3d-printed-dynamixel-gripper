from copy import deepcopy

import pytest

from gripper_design.fastener_ledger import (
    FastenerLedgerError,
    load_fastener_ledger,
    validate_fastener_ledger,
)


def test_jaw_fastener_ledger_inventories_every_interface_and_stays_unknown():
    ledger = load_fastener_ledger()

    assert ledger["release"]["all_fastener_interfaces_inventoried"] is True
    assert ledger["release"]["hardware_selected"] is False
    assert all(
        interface["dimensions_confirmed"] is False for interface in ledger["interfaces"].values()
    )
    assert all(
        status != "PASS"
        for interface in ledger["interfaces"].values()
        for key, status in interface.items()
        if key.endswith("_status")
    )


def test_unconfirmed_interface_cannot_be_promoted_to_pass():
    ledger = deepcopy(load_fastener_ledger())
    ledger["interfaces"]["xl430_output_side"]["tool_status"] = "PASS"

    with pytest.raises(FastenerLedgerError, match="cannot PASS"):
        validate_fastener_ledger(ledger)


def test_omitted_opposite_support_is_rejected():
    ledger = deepcopy(load_fastener_ledger())
    del ledger["interfaces"]["pinion_opposite_support_axis"]

    with pytest.raises(FastenerLedgerError, match="every changed support"):
        validate_fastener_ledger(ledger)
