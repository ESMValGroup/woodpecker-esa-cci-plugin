import dask.array as da
import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.mask_flag_values"
# Like the snow water equivalent, where 0 means no snow.
OPTIONS = {FIX_ID: {"variables": {"swe": {"valid_min": 0}}}}


@pytest.fixture
def dataset() -> xr.Dataset:
    return xr.Dataset(
        {
            "swe": (
                "x",
                np.array([12.0, -30.0, 0.0, -10.0, 5.0]),
                {
                    "flag_values": np.array([-30, -10, 0], dtype="int32"),
                    "flag_meanings": "Glacier Water no_snow",
                    "units": "mm",
                },
            ),
        }
    )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_flags_are_masked(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["swe has flags in its data"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert float(dataset["swe"][1]) == -30

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    np.testing.assert_array_equal(
        dataset["swe"], [12.0, np.nan, 0.0, np.nan, 5.0]
    )
    assert dataset["swe"].attrs == {"units": "mm"}
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_integer_data_above_maximum_is_masked(dataset: xr.Dataset) -> None:
    # Like the snow cover fraction in percent, with flags from 205, some of
    # which are not listed.
    dataset["swe"] = dataset["swe"].astype("int16")
    dataset["swe"].values[[0, 4]] = [205, 253]
    options = {FIX_ID: {"variables": {"swe": {"valid_max": 100}}}}

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=options)
    np.testing.assert_array_equal(
        dataset["swe"], [np.nan, -30.0, 0.0, -10.0, np.nan]
    )
    assert dataset["swe"].dtype == np.float32


def test_data_stays_lazy(dataset: xr.Dataset) -> None:
    dataset = dataset.chunk()

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert dataset["swe"].chunks is not None


def test_large_data_is_not_loaded() -> None:
    # Like the daily snow datasets: about 50 GB in memory.
    data = da.zeros((8000, 1800, 3600), chunks=(1, 1800, 3600))
    dataset = xr.Dataset(
        {"swe": (("time", "lat", "lon"), data, {"flag_values": [-1]})}
    )

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert isinstance(dataset["swe"].data, da.Array)


def test_missing_variable_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variables": {"scfg": {"valid_max": 100}}}}

    with pytest.raises(ValueError, match="scfg: it does not exist"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_range_is_required() -> None:
    fix = FixFunctionRegistry.instantiate(FIX_ID)

    with pytest.raises(ValueError, match="Set valid_min, valid_max or both"):
        fix.configure({"variables": {"swe": {}}})
