import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.set_time_units"
UNITS = "days since 1850-01-01"
OPTIONS = {FIX_ID: {"coordinate": "time", "units": UNITS}}


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    ("options", "match"),
    [
        ({"coordinate": "time"}, "units or calendar option must be set"),
        ({"coordinate": "t", "units": UNITS}, "t: it does not exist"),
        (
            {"coordinate": "lat", "units": UNITS},
            "lat: it does not contain times",
        ),
    ],
)
def test_invalid_coordinate_raises(
    tcwv_dataset: xr.Dataset,
    options: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options={FIX_ID: options})


def test_time_units_are_set(tcwv_dataset: xr.Dataset) -> None:
    original = tcwv_dataset["time"].copy()

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert tcwv_dataset["time"].encoding["units"] != UNITS

    result = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    xr.testing.assert_identical(tcwv_dataset["time"], original)
    for name in ("time", "time_bnds"):
        encoding = tcwv_dataset[name].encoding
        assert encoding["units"] == UNITS
        assert encoding["dtype"] == np.float64
        assert encoding["calendar"] == "gregorian"
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)

    # The times are written in the new units.
    variables, _ = xr.conventions.cf_encoder(
        dict(tcwv_dataset.variables), tcwv_dataset.attrs
    )
    time = variables["time"]
    assert time.attrs["units"] == UNITS
    days = (original - np.datetime64("1850-01-01")) / np.timedelta64(1, "D")
    np.testing.assert_allclose(time.to_numpy(), days)


def test_calendar_is_set(tcwv_dataset: xr.Dataset) -> None:
    original = {
        name: dict(tcwv_dataset[name].encoding)
        for name in ("time", "time_bnds")
    }
    options = {FIX_ID: {"coordinate": "time", "calendar": "standard"}}

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)
    assert findings.fix_ids == (FIX_ID,)

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    # Only the calendar changes, so the times keep their integer storage.
    for name, encoding in original.items():
        assert tcwv_dataset[name].encoding == {
            **encoding,
            "calendar": "standard",
        }
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


def test_undecoded_times_are_converted(tcwv_dataset: xr.Dataset) -> None:
    original = tcwv_dataset[["time", "time_bnds"]].copy(deep=True)
    for name in ("time", "time_bnds"):
        tcwv_dataset[name] = xr.conventions.encode_cf_variable(
            tcwv_dataset[name].variable, name=name
        )
    assert tcwv_dataset["time"].attrs["units"] != UNITS
    # CF allows bounds to inherit the units and calendar of their coordinate.
    for key in ("units", "calendar"):
        del tcwv_dataset["time_bnds"].attrs[key]
    options = {
        FIX_ID: {"coordinate": "time", "units": UNITS, "calendar": "standard"}
    }

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)
    assert findings.fix_ids == (FIX_ID,) * 2

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    for name in ("time", "time_bnds"):
        variable = tcwv_dataset[name].variable
        assert variable.attrs["units"] == UNITS
        assert variable.attrs["calendar"] == "standard"
        assert variable.dtype == np.float64
        assert "_FillValue" not in variable.attrs
        decoded = xr.conventions.decode_cf_variable(name, variable)
        np.testing.assert_array_equal(decoded, original[name])
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)
