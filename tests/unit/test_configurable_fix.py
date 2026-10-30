import pytest
import xarray as xr
from pydantic import ValidationError
from woodpecker.fixes.registry import FixFunctionRegistry

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix

FIX_IDS = [
    fix_id
    for fix_id in FixFunctionRegistry.registered_ids()
    if fix_id.startswith("esa_cci.")
]


def _has_options(fix_id: str) -> bool:
    fix = FixFunctionRegistry.instantiate(fix_id)
    return isinstance(fix, ConfigurableFix) and bool(
        fix.options_model.model_fields
    )


# The fixes with options, which do nothing until they are configured.
CONFIGURABLE_FIX_IDS = [fix_id for fix_id in FIX_IDS if _has_options(fix_id)]


def test_all_plugin_fixes_are_found() -> None:
    assert len(FIX_IDS) == 25


@pytest.mark.parametrize("fix_id", FIX_IDS)
def test_unknown_option_raises(fix_id: str) -> None:
    fix = FixFunctionRegistry.instantiate(fix_id)

    with pytest.raises(ValidationError, match="unknown_option"):
        fix.configure({"unknown_option": 1})


@pytest.mark.parametrize("fix_id", CONFIGURABLE_FIX_IDS)
def test_unconfigured_fix_does_nothing(
    fix_id: str,
    tcwv_dataset: xr.Dataset,
) -> None:
    # Woodpecker only calls check and apply when the fix matches, so call
    # them directly.
    fix = FixFunctionRegistry.instantiate(fix_id)
    original = tcwv_dataset.copy(deep=True)

    assert not fix.matches(tcwv_dataset)
    assert fix.check(tcwv_dataset) == []
    assert not fix.apply(tcwv_dataset, dry_run=False)
    xr.testing.assert_identical(tcwv_dataset, original)
