import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.center_daily_time"
OPTIONS = {FIX_ID: {"coordinate": "time"}}
DAYS = np.arange("2002-07-01", "2002-07-05", dtype="datetime64[D]")
BOUNDS = np.stack([DAYS[:-1], DAYS[1:]], axis=1).astype("datetime64[ns]")
MIDDLE = (DAYS[:-1] + np.timedelta64(12, "h")).astype("datetime64[ns]")
TIME_ENCODING = {
    "dtype": np.dtype("int32"),
    "units": "days since 1970-01-01",
    "calendar": "gregorian",
}


@pytest.fixture
def daily_dataset() -> xr.Dataset:
    """Return a daily dataset with time points at the start of the day.

    Like the daily ESA CCI water vapour datasets in Kerchunk format.
    """
    dataset = xr.Dataset(
        {"tcwv": (("time",), np.ones(BOUNDS.shape[0], dtype="float32"))},
        coords={
            "time": ("time", BOUNDS[:, 0], {"bounds": "time_bnds"}),
            "time_bnds": (("time", "nv"), BOUNDS),
        },
    )
    for name in ("time", "time_bnds"):
        dataset[name].encoding = dict(TIME_ENCODING)
    return dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(daily_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(daily_dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    "decode_times", [True, False], ids=["decoded", "not_decoded"]
)
def test_time_is_centered(
    daily_dataset: xr.Dataset,
    decode_times: bool,  # noqa: FBT001
) -> None:
    if not decode_times:
        for name in ("time", "time_bnds"):
            daily_dataset[name] = xr.conventions.encode_cf_variable(
                daily_dataset[name].variable, name=name
            )
    original = daily_dataset["time"].copy()

    findings = woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_identical(daily_dataset["time"], original)

    result = woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert not woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)

    decoded = xr.decode_cf(daily_dataset[["time", "time_bnds"]])
    np.testing.assert_array_equal(decoded["time"], MIDDLE)
    np.testing.assert_array_equal(decoded["time_bnds"], BOUNDS)
    # The data stays at the same time step.
    np.testing.assert_array_equal(daily_dataset["tcwv"], 1.0)


def test_bounds_are_added(daily_dataset: xr.Dataset) -> None:
    del daily_dataset["time"].attrs["bounds"]
    daily_dataset = daily_dataset.drop_vars("time_bnds")

    woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert daily_dataset["time"].attrs["bounds"] == "time_bnds"
    assert daily_dataset["time_bnds"].dims == ("time", "bnds")
    np.testing.assert_array_equal(daily_dataset["time"], MIDDLE)
    np.testing.assert_array_equal(daily_dataset["time_bnds"], BOUNDS)
    assert not woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)


def test_centered_time_is_not_changed(daily_dataset: xr.Dataset) -> None:
    daily_dataset["time"] = daily_dataset["time"].copy(data=MIDDLE)

    assert not woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    ("coordinate", "match"),
    [
        ("t", "t in calendar days: it does not exist"),
        (
            "time_bnds",
            "time_bnds in calendar days: it is not a dimension coordinate",
        ),
        ("tcwv", "tcwv in calendar days: it is not a dimension coordinate"),
    ],
)
def test_invalid_coordinate_raises(
    daily_dataset: xr.Dataset,
    coordinate: str,
    match: str,
) -> None:
    options = {FIX_ID: {"coordinate": coordinate}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(daily_dataset, fixes=FIX_ID, options=options)


def test_times_in_the_same_day_raise(daily_dataset: xr.Dataset) -> None:
    times = daily_dataset["time"].to_numpy().copy()
    times[1] = times[0] + np.timedelta64(1, "h")
    daily_dataset["time"] = daily_dataset["time"].copy(data=times)

    with pytest.raises(
        ValueError, match="several time points in the same day"
    ):
        woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)
