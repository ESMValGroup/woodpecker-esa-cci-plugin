import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.add_bounds"
OPTIONS = {FIX_ID: {"coordinates": ["lat", "lon"]}}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    """Remove the latitude and longitude bounds, like in the SST dataset."""
    for name in ("lat", "lon"):
        del tcwv_dataset[name].attrs["bounds"]
    return tcwv_dataset.drop_vars(["lat_bnds", "lon_bnds"])


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_bounds_are_added(
    dataset: xr.Dataset, tcwv_dataset: xr.Dataset
) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["lat has no bounds", "lon has no bounds"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "lat_bnds" not in dataset

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    for name in ("lat", "lon"):
        bounds = dataset[name].attrs["bounds"]
        assert bounds == f"{name}_bnds"
        assert dataset[bounds].dims == (name, "bnds")
        # The synthetic dataset has the bounds of the real dataset.
        np.testing.assert_allclose(dataset[bounds], tcwv_dataset[bounds])
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_existing_bounds_are_kept(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    ("coordinate", "match"),
    [
        ("latitude", "latitude: it does not exist"),
        ("time_bnds", "time_bnds: it is not a dimension coordinate"),
        ("lat", "lat: its step size is not fixed"),
    ],
)
def test_invalid_coordinate_raises(
    dataset: xr.Dataset,
    coordinate: str,
    match: str,
) -> None:
    lat = dataset["lat"].to_numpy().copy()
    lat[-1] += 1.0
    dataset["lat"] = dataset["lat"].copy(data=lat)
    options = {FIX_ID: {"coordinates": [coordinate]}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_single_value_raises(dataset: xr.Dataset) -> None:
    dataset = dataset.isel(lat=slice(0, 1))

    with pytest.raises(ValueError, match="lat: it has less than 2 values"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_existing_bounds_variable_raises(dataset: xr.Dataset) -> None:
    dataset["lat_bnds"] = dataset["lat"]

    with pytest.raises(ValueError, match="lat: lat_bnds already exists"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
