import dask.array as da
import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.apply_valid_range"
OPTIONS = {FIX_ID: {"variables": ["toz"]}}


@pytest.fixture
def dataset() -> xr.Dataset:
    # Like the total ozone column, with missing values stored as -9.9.
    return xr.Dataset(
        {
            "toz": (
                "x",
                np.array([300.0, -9.9, 50.0, 700.0, np.nan]),
                {"valid_range": [50.0, 650.0], "units": "DU"},
            ),
        }
    )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_values_outside_valid_range_are_masked(dataset: xr.Dataset) -> None:
    dataset = dataset.chunk()
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["toz may have values outside its valid range"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert float(dataset["toz"][1]) == -9.9

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert isinstance(dataset["toz"].data, da.Array)
    np.testing.assert_array_equal(
        dataset["toz"], [300.0, np.nan, 50.0, np.nan, np.nan]
    )
    assert dataset["toz"].attrs == {"units": "DU"}
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_valid_min_and_max(dataset: xr.Dataset) -> None:
    dataset["toz"] = ("x", np.array([300, -10, 50, 700], dtype="int16"))
    dataset["toz"].attrs = {"valid_min": np.int16(0), "valid_max": 650}

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)

    np.testing.assert_array_equal(
        dataset["toz"], [300.0, np.nan, 50.0, np.nan]
    )
    assert dataset["toz"].dtype == np.float32
    assert dataset["toz"].attrs == {}


def test_missing_variable_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variables": ["o3"]}}
    with pytest.raises(ValueError, match="o3: it does not exist"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_packed_variable_raises(dataset: xr.Dataset) -> None:
    dataset["toz"].encoding["scale_factor"] = 0.1
    with pytest.raises(ValueError, match="toz: it is packed"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
