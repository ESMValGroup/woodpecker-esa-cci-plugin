import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.select_time_steps"
OPTIONS = {FIX_ID: {"coordinate": "time", "day_of_month": 15}}
# Like the sea surface salinity: 30-day means every 15 days.
TIMES = np.array(
    ["2010-01-15", "2010-02-01", "2010-02-15", "2010-03-01", "2010-03-15"],
    dtype="datetime64[ns]",
)


@pytest.fixture
def dataset() -> xr.Dataset:
    return xr.Dataset(
        {
            "sss": (("time", "lat"), np.arange(10.0).reshape(5, 2)),
            "lat_bnds": (("lat", "bnds"), [[-1.0, 0.0], [0.0, 1.0]]),
        },
        coords={
            "time": ("time", TIMES, {"standard_name": "time"}),
            "lat": ("lat", [-0.5, 0.5]),
        },
    )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    "decode_times", [True, False], ids=["decoded", "not_decoded"]
)
def test_time_steps_are_selected(
    dataset: xr.Dataset,
    decode_times: bool,  # noqa: FBT001
) -> None:
    if not decode_times:
        dataset["time"] = xr.conventions.encode_cf_variable(
            dataset["time"].variable, name="time"
        )

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        "time has 2 time points that are not on day 15 of the month"
    ]
    # Woodpecker adds the source_name attribute in the check.
    original = dataset.copy(deep=True)

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_identical(dataset, original)

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    decoded = xr.decode_cf(dataset) if not decode_times else dataset
    np.testing.assert_array_equal(decoded["time"], TIMES[[0, 2, 4]])
    np.testing.assert_array_equal(dataset["sss"], [[0, 1], [4, 5], [8, 9]])
    assert dataset["time"].attrs == original["time"].attrs
    xr.testing.assert_identical(dataset["lat_bnds"], original["lat_bnds"])
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_missing_coordinate_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"coordinate": "t", "day_of_month": 15}}

    with pytest.raises(ValueError, match="t: it does not exist"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_auxiliary_coordinate_raises(dataset: xr.Dataset) -> None:
    dataset = dataset.assign_coords(day=("time", TIMES))
    options = {FIX_ID: {"coordinate": "day", "day_of_month": 15}}

    with pytest.raises(ValueError, match="not a dimension coordinate"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_invalid_day_raises() -> None:
    fix = FixFunctionRegistry.instantiate(FIX_ID)

    with pytest.raises(ValueError, match="less than or equal to 31"):
        fix.configure({"coordinate": "time", "day_of_month": 32})
