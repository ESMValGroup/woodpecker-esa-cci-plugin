import dask.array as da
import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.sum_variables"
OPTIONS = {FIX_ID: {"sums": {"cwp_allsky": ["lwp_allsky", "iwp_allsky"]}}}


@pytest.fixture
def dataset() -> xr.Dataset:
    # Like the cloud datasets, with a liquid and ice water path.
    return xr.Dataset(
        {
            "lwp_allsky": (
                ("time", "lat"),
                np.array([[1.0, 2.0], [np.nan, 4.0]]),
                {"units": "g/m2", "long_name": "liquid", "valid_max": 1.0},
            ),
            "iwp_allsky": (
                ("time", "lat"),
                np.array([[10.0, 20.0], [30.0, np.nan]]),
                {"units": "g/m2", "long_name": "ice", "valid_max": 1.0},
            ),
            "other": ("time", np.array([1.0, 2.0])),
        }
    ).chunk({"time": 1})


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_variables_are_replaced_by_their_sum(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        "cwp_allsky is missing, the sum of lwp_allsky, iwp_allsky"
    ]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "cwp_allsky" not in dataset

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert set(dataset.data_vars) == {"cwp_allsky", "other"}
    total = dataset["cwp_allsky"]
    assert isinstance(total.data, da.Array)
    assert total.dims == ("time", "lat")
    # The sum is unknown where one of the terms is missing.
    np.testing.assert_array_equal(total, [[11.0, 22.0], [np.nan, np.nan]])
    assert total.attrs == {"units": "g/m2"}
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_missing_term_raises(dataset: xr.Dataset) -> None:
    del dataset["iwp_allsky"]
    with pytest.raises(ValueError, match="iwp_allsky do not exist"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_existing_variable_raises(dataset: xr.Dataset) -> None:
    dataset["cwp_allsky"] = dataset["lwp_allsky"]
    with pytest.raises(ValueError, match="cwp_allsky: it already exists"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize("units", ["kg m-2", None])
def test_different_units_raise(
    dataset: xr.Dataset,
    units: str | None,
) -> None:
    if units is None:
        del dataset["iwp_allsky"].attrs["units"]
    else:
        dataset["iwp_allsky"].attrs["units"] = units
    with pytest.raises(ValueError, match="do not have the same units"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_single_term_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"sums": {"cwp_allsky": ["lwp_allsky"]}}}
    with pytest.raises(ValueError, match="at least 2 items"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)
