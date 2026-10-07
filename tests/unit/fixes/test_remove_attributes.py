import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.remove_attributes"
OPTIONS = {
    FIX_ID: {
        "attributes": {
            "crs": ["standard_name"],
            "lat_bnds": ["standard_name", "long_name", "units_metadata"],
        },
    }
}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_attributes_are_removed(dataset: xr.Dataset) -> None:
    original = {
        name: dict(variable.attrs)
        for name, variable in dataset.variables.items()
    }

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    # Attributes that do not exist are ignored.
    assert messages == [
        "crs has attributes standard_name",
        "lat_bnds has attributes standard_name, long_name",
    ]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert dataset["crs"].attrs == original["crs"]

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert "standard_name" not in dataset["crs"].attrs
    assert not {"standard_name", "long_name"} & set(dataset["lat_bnds"].attrs)
    # Other attributes are kept.
    assert dataset["lon_bnds"].attrs == original["lon_bnds"]
    assert dataset["crs"].attrs["long_name"] == original["crs"]["long_name"]
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_missing_variable_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"attributes": {"prw": ["standard_name"]}}}

    with pytest.raises(ValueError, match="prw: it does not exist"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)
