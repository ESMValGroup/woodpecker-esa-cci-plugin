import pytest
import woodpecker
import xarray as xr
from pydantic import ValidationError
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.set_global_attributes"
OPTIONS = {
    FIX_ID: {
        "attributes": {"Conventions": "CF-1.11", "naming_authority": "ESACCI"},
    }
}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset.attrs["Conventions"] = "CF-1.7"
    tcwv_dataset.attrs.pop("naming_authority", None)
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_attribute_without_value_raises() -> None:
    fix = FixFunctionRegistry.instantiate(FIX_ID)

    with pytest.raises(ValidationError, match="comment have no value"):
        fix.configure({"attributes": {"comment": None}})


def test_attributes_are_set(dataset: xr.Dataset) -> None:
    original = dict(dataset.attrs)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,) * 2

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert dataset.attrs["Conventions"] == "CF-1.7"
    assert "naming_authority" not in dataset.attrs

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert dataset.attrs["Conventions"] == "CF-1.11"
    assert dataset.attrs["naming_authority"] == "ESACCI"
    assert dataset.attrs["title"] == original["title"]
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
