import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.center_monthly_time"
OPTIONS = {FIX_ID: {"coordinate": "time"}}
# The months of the synthetic dataset.
MONTHS = np.arange("2002-07", "2002-11", dtype="datetime64[M]")
BOUNDS = np.stack([MONTHS[:-1], MONTHS[1:]], axis=1).astype("datetime64[ns]")
MIDDLE = np.array(
    ["2002-07-16T12", "2002-08-16T12", "2002-09-16"], dtype="datetime64[ns]"
)


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
        ("t", "t in calendar months: it does not exist"),
        (
            "time_bnds",
            "time_bnds in calendar months: it is not a dimension coordinate",
        ),
        ("lat", "lat in calendar months: it is not decoded"),
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

    with pytest.raises(ValueError, match="several time points in the same"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
