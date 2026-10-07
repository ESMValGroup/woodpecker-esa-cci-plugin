import pytest
from pydantic import ValidationError
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_IDS = [
    fix_id
    for fix_id in FixFunctionRegistry.registered_ids()
    if fix_id.startswith("esa_cci.")
]


def test_all_plugin_fixes_are_found() -> None:
    assert len(FIX_IDS) == 11


@pytest.mark.parametrize("fix_id", FIX_IDS)
def test_unknown_option_raises(fix_id: str) -> None:
    fix = FixFunctionRegistry.instantiate(fix_id)

    with pytest.raises(ValidationError, match="unknown_option"):
        fix.configure({"unknown_option": 1})
