import dask.array as da
import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.convert_relative_uncertainties"
OPTIONS = {FIX_ID: {"uncertainties": {"o3_error": "o3"}}}


@pytest.fixture
def dataset() -> xr.Dataset:
    # Like the ozone limb profiles, with the uncertainty in percent of the
    # mixing ratio.
    return xr.Dataset(
        {
            "o3": (
                ("time", "plev"),
                np.array([[2e-6, 4e-6], [-1e-6, np.nan]]),
                {"units": "mol mol-1"},
            ),
            "o3_error": (
                ("time", "plev"),
                np.array([[10.0, 5.0], [-20.0, 3.0]], dtype="float32"),
                {"units": "%", "valid_min": 0.0, "long_name": "error"},
            ),
        }
    ).chunk({"time": 1})


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_uncertainties_are_converted(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["o3_error is relative to o3"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert dataset["o3_error"].attrs["units"] == "%"

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    error = dataset["o3_error"]
    assert isinstance(error.data, da.Array)
    assert error.dims == ("time", "plev")
    np.testing.assert_allclose(error, [[2e-7, 2e-7], [2e-7, np.nan]])
    assert error.attrs == {"units": "mol mol-1", "long_name": "error"}
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_missing_variable_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"uncertainties": {"o3_error": "toz"}}}
    with pytest.raises(ValueError, match="toz does not exist"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_missing_units_raise(dataset: xr.Dataset) -> None:
    del dataset["o3"].attrs["units"]
    with pytest.raises(ValueError, match="o3 has no units"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_units_with_dimension_raise(dataset: xr.Dataset) -> None:
    dataset["o3_error"].attrs["units"] = "m"
    with pytest.raises(ValueError, match="'m' are not dimensionless"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
