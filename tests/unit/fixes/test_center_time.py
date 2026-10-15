import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.center_time"
OPTIONS = {FIX_ID: {"coordinate": "time"}}
# The months of the synthetic dataset.
MONTHS = np.arange("2002-07", "2002-11", dtype="datetime64[M]")
BOUNDS = np.stack([MONTHS[:-1], MONTHS[1:]], axis=1).astype("datetime64[ns]")
MIDDLE = np.array(
    ["2002-07-16T12", "2002-08-16T12", "2002-09-16"], dtype="datetime64[ns]"
)
# The days of the daily dataset.
DAYS = np.arange("2002-07-01", "2002-07-05", dtype="datetime64[D]")
DAILY_BOUNDS = np.stack([DAYS[:-1], DAYS[1:]], axis=1).astype("datetime64[ns]")
DAILY_MIDDLE = (DAYS[:-1] + np.timedelta64(12, "h")).astype("datetime64[ns]")
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
        {"tcwv": (("time",), np.ones(DAILY_BOUNDS.shape[0], dtype="float32"))},
        coords={
            "time": ("time", DAILY_BOUNDS[:, 0], {"bounds": "time_bnds"}),
            "time_bnds": (("time", "nv"), DAILY_BOUNDS),
        },
    )
    for name in ("time", "time_bnds"):
        dataset[name].encoding = dict(TIME_ENCODING)
    return dataset


def _undecode(dataset: xr.Dataset) -> None:
    for name in ("time", "time_bnds"):
        dataset[name] = xr.conventions.encode_cf_variable(
            dataset[name].variable, name=name
        )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    "decode_times", [True, False], ids=["decoded", "not_decoded"]
)
def test_time_is_centered(
    tcwv_dataset: xr.Dataset,
    decode_times: bool,  # noqa: FBT001
) -> None:
    tcwv_dataset["time"].encoding["units"] = "days since 1850-01-01"
    if not decode_times:
        _undecode(tcwv_dataset)
    original = tcwv_dataset["time"].copy()

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_identical(tcwv_dataset["time"], original)

    result = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)

    decoded = xr.decode_cf(tcwv_dataset[["time", "time_bnds"]])
    np.testing.assert_array_equal(decoded["time"], MIDDLE)
    np.testing.assert_array_equal(decoded["time_bnds"], BOUNDS)
    assert decoded["time"].encoding["units"] == "days since 1850-01-01"
    for name in ("time", "time_bnds"):
        assert "_FillValue" not in tcwv_dataset[name].attrs


def test_bounds_are_added(tcwv_dataset: xr.Dataset) -> None:
    del tcwv_dataset["time"].attrs["bounds"]
    tcwv_dataset = tcwv_dataset.drop_vars("time_bnds")

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert tcwv_dataset["time"].attrs["bounds"] == "time_bnds"
    assert tcwv_dataset["time_bnds"].dims == ("time", "bnds")
    np.testing.assert_array_equal(tcwv_dataset["time_bnds"], BOUNDS)
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    ("coordinate", "match"),
    [
        ("t", "t: it does not exist"),
        ("time_bnds", "time_bnds: it is not a dimension coordinate"),
        ("lat", "lat: it is not decoded"),
    ],
)
def test_invalid_coordinate_raises(
    tcwv_dataset: xr.Dataset,
    coordinate: str,
    match: str,
) -> None:
    options = {FIX_ID: {"coordinate": coordinate}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


def test_times_in_the_same_month_raise(tcwv_dataset: xr.Dataset) -> None:
    times = tcwv_dataset["time"].to_numpy().copy()
    times[1] = times[0] + np.timedelta64(1, "D")
    tcwv_dataset["time"] = tcwv_dataset["time"].copy(data=times)
    # Otherwise, the frequency would be determined as daily.
    options = {FIX_ID: {"coordinate": "time", "frequency": "mon"}}

    with pytest.raises(ValueError, match="several time points in the same"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


@pytest.mark.parametrize(
    "decode_times", [True, False], ids=["decoded", "not_decoded"]
)
@pytest.mark.parametrize(
    "frequency", [None, "day"], ids=["inferred", "configured"]
)
def test_daily_time_is_centered(
    daily_dataset: xr.Dataset,
    decode_times: bool,  # noqa: FBT001
    frequency: str | None,
) -> None:
    if not decode_times:
        _undecode(daily_dataset)
    options = {FIX_ID: {"coordinate": "time", "frequency": frequency}}

    findings = woodpecker.check(daily_dataset, fixes=FIX_ID, options=options)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        (
            "time is not centered in calendar days, or its bounds are not "
            "whole calendar days"
        )
    ]

    woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    assert not woodpecker.check(daily_dataset, fixes=FIX_ID, options=options)
    decoded = xr.decode_cf(daily_dataset[["time", "time_bnds"]])
    np.testing.assert_array_equal(decoded["time"], DAILY_MIDDLE)
    np.testing.assert_array_equal(decoded["time_bnds"], DAILY_BOUNDS)
    # The data stays at the same time step.
    np.testing.assert_array_equal(daily_dataset["tcwv"], 1.0)


def test_centered_daily_time_is_not_changed(
    daily_dataset: xr.Dataset,
) -> None:
    daily_dataset["time"] = daily_dataset["time"].copy(data=DAILY_MIDDLE)

    assert not woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)


def test_daily_bounds_are_added(daily_dataset: xr.Dataset) -> None:
    del daily_dataset["time"].attrs["bounds"]
    daily_dataset = daily_dataset.drop_vars("time_bnds")

    woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert daily_dataset["time"].attrs["bounds"] == "time_bnds"
    np.testing.assert_array_equal(daily_dataset["time"], DAILY_MIDDLE)
    np.testing.assert_array_equal(daily_dataset["time_bnds"], DAILY_BOUNDS)


def test_daily_time_with_gaps_is_centered(daily_dataset: xr.Dataset) -> None:
    # One of the two time steps is two days.
    times = daily_dataset["time"].to_numpy().copy()
    times[2:] += np.timedelta64(1, "D")
    daily_dataset = daily_dataset.drop_vars("time_bnds")
    daily_dataset["time"] = daily_dataset["time"].copy(data=times)
    del daily_dataset["time"].attrs["bounds"]

    woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    np.testing.assert_array_equal(
        daily_dataset["time"], times + np.timedelta64(12, "h")
    )


def test_single_time_point_uses_bounds(daily_dataset: xr.Dataset) -> None:
    daily_dataset = daily_dataset.isel(time=slice(1))

    woodpecker.apply(
        daily_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    np.testing.assert_array_equal(daily_dataset["time"], DAILY_MIDDLE[:1])


def test_configured_frequency_is_used(tcwv_dataset: xr.Dataset) -> None:
    # A single month, with times in the same month that are a day apart,
    # would be daily.
    options = {FIX_ID: {"coordinate": "time", "frequency": "mon"}}

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        (
            "time is not centered in calendar months, or its bounds are not "
            "whole calendar months"
        )
    ]


@pytest.mark.parametrize(
    ("step", "match"),
    [
        (None, "from a single time point without bounds"),
        (np.timedelta64(7, "D"), "from its time step of 7 days"),
    ],
)
def test_unknown_frequency_raises(
    daily_dataset: xr.Dataset,
    step: np.timedelta64 | None,
    match: str,
) -> None:
    daily_dataset = daily_dataset.drop_vars("time_bnds")
    del daily_dataset["time"].attrs["bounds"]
    if step is None:
        daily_dataset = daily_dataset.isel(time=slice(1))
    else:
        times = DAYS[0] + step * np.arange(daily_dataset.sizes["time"])
        daily_dataset["time"] = daily_dataset["time"].copy(
            data=times.astype("datetime64[ns]")
        )

    with pytest.raises(ValueError, match=match):
        woodpecker.check(daily_dataset, fixes=FIX_ID, options=OPTIONS)


def test_invalid_frequency_raises(tcwv_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"coordinate": "time", "frequency": "yr"}}

    with pytest.raises(ValueError, match="frequency"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)
