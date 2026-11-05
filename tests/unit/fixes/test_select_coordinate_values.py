import dask.array as da
import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.select_coordinate_values"
VALUES = [100000.0, 30000.0, 20000.0, 70.0, 3.0]
OPTIONS = {FIX_ID: {"coordinate": "air_pressure", "values": VALUES}}


@pytest.fixture
def dataset() -> xr.Dataset:
    # Like the ozone limb profiles, on pressure levels in single precision,
    # of which some are requested by CMIP7.
    pressure = np.array([30000.0, 25000.0, 20000.0, 70.0], dtype="float32")
    # Single precision values that are not exactly the requested values.
    pressure[-1] = np.float32(0.7) * np.float32(100)
    return xr.Dataset(
        {
            "o3": (
                ("time", "air_pressure"),
                np.arange(8.0).reshape(2, 4),
                {"units": "1"},
            ),
            "altitude": ("air_pressure", np.arange(4.0)),
            "time_bnds": (("time", "bnds"), np.zeros((2, 2))),
        },
        coords={
            "air_pressure": (
                "air_pressure",
                pressure,
                {"units": "Pa", "standard_name": "air_pressure"},
            ),
        },
    ).chunk({"time": 1})


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_values_are_selected(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["air_pressure does not have the configured values"]
    # Woodpecker adds the source_name attribute in the check.
    original = dataset.copy(deep=True)

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_identical(dataset, original)

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    pressure = dataset["air_pressure"]
    np.testing.assert_array_equal(pressure, VALUES)
    assert pressure.dtype == np.float64
    assert pressure.attrs == original["air_pressure"].attrs
    assert "air_pressure" in dataset.indexes
    o3 = dataset["o3"]
    assert isinstance(o3.data, da.Array)
    np.testing.assert_array_equal(
        o3,
        [[np.nan, 0.0, 2.0, 3.0, np.nan], [np.nan, 4.0, 6.0, 7.0, np.nan]],
    )
    assert o3.attrs == original["o3"].attrs
    np.testing.assert_array_equal(
        dataset["altitude"], [np.nan, 0.0, 2.0, 3.0, np.nan]
    )
    xr.testing.assert_identical(dataset["time_bnds"], original["time_bnds"])
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    ("coordinate", "message"),
    [
        ("plev", "it does not exist"),
        ("altitude", "it is not a dimension coordinate"),
    ],
)
def test_invalid_coordinate_raises(
    dataset: xr.Dataset, coordinate: str, message: str
) -> None:
    dataset = dataset.drop_vars("air_pressure").set_coords("altitude")
    options = {FIX_ID: {"coordinate": coordinate, "values": VALUES}}
    with pytest.raises(ValueError, match=message):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_coordinate_with_bounds_raises(dataset: xr.Dataset) -> None:
    dataset["air_pressure"].attrs["bounds"] = "air_pressure_bnds"
    with pytest.raises(ValueError, match="it has bounds"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
