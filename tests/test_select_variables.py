import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.select_variables"
OPTIONS = {FIX_ID: {"variables": ["tcwv"]}}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    """Add variables that tcwv refers to and variables it does not."""
    tcwv_dataset["tcwv"].attrs["ancillary_variables"] = "stdv"
    tcwv_dataset["tcwv"].attrs["grid_mapping"] = "crs"
    tcwv_dataset["stdv"] = tcwv_dataset["tcwv"].copy()
    tcwv_dataset["tcwv_err"] = tcwv_dataset["tcwv"].copy()
    tcwv_dataset["crs"] = xr.DataArray(0)
    lat = tcwv_dataset["lat"].to_numpy()
    tcwv_dataset["lat_bnds"] = (
        ("lat", "nv"),
        np.column_stack([lat - 0.5, lat + 0.5]),
    )
    tcwv_dataset["lat"].attrs["bounds"] = "lat_bnds"
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_missing_variable_keeps_everything(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variables": ["prw"]}}

    assert not woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_invalid_option_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variables": "tcwv"}}

    with pytest.raises(TypeError, match="variables option"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_referenced_variables_are_kept(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "tcwv_err" in dataset

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert set(dataset.data_vars) == {"tcwv", "stdv", "crs", "lat_bnds"}
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
