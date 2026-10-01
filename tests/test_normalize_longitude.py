import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.normalize_longitude"
OPTIONS = {FIX_ID: {"coordinate": "lon"}}


@pytest.fixture
def dataset() -> xr.Dataset:
    """Return a dataset with longitudes in the range [-180, 180)."""
    lon = (np.arange(-180.0, 180.0, 90.0) + 45.0).astype("float32")
    return xr.Dataset(
        {
            "tcwv": (("lat", "lon"), np.array([[1.0, 2.0, 3.0, 4.0]])),
            "lon_bnds": (
                ("lon", "nv"),
                np.column_stack([lon - 45.0, lon + 45.0]),
                {"valid_min": -180.0, "valid_max": 180.0},
            ),
        },
        coords={
            "lat": [0.0],
            "lon": (
                "lon",
                lon,
                {
                    "units": "degrees_east",
                    "bounds": "lon_bnds",
                    "valid_range": [-180.0, 180.0],
                },
            ),
            "lon_label": ("lon", ["a", "b", "c", "d"]),
        },
    )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_invalid_option_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"coordinate": 1}}

    with pytest.raises(TypeError, match="coordinate option"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


@pytest.mark.parametrize(
    ("coordinate", "match"),
    [
        ("longitude", "it does not exist"),
        ("lon_label", "it is not a dimension coordinate"),
    ],
)
def test_invalid_coordinate_raises(
    dataset: xr.Dataset,
    coordinate: str,
    match: str,
) -> None:
    options = {FIX_ID: {"coordinate": coordinate}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_longitude_is_wrapped(dataset: xr.Dataset) -> None:
    original = dataset.copy(deep=True)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_equal(dataset, original)

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    np.testing.assert_array_equal(dataset["lon"], [45, 135, 225, 315])
    np.testing.assert_array_equal(dataset.indexes["lon"], [45, 135, 225, 315])
    assert dataset["lon"].dtype == np.float32
    # The range attributes no longer match, so they are removed.
    assert dataset["lon"].attrs == {
        "units": "degrees_east",
        "bounds": "lon_bnds",
    }
    np.testing.assert_array_equal(
        dataset["lon_bnds"], [[0, 90], [90, 180], [180, 270], [270, 360]]
    )
    assert dataset["lon_bnds"].dtype == np.float32
    assert dataset["lon_bnds"].attrs == {}
    np.testing.assert_array_equal(dataset["tcwv"], [[3.0, 4.0, 1.0, 2.0]])
    np.testing.assert_array_equal(dataset["lon_label"], ["c", "d", "a", "b"])
    assert "lon_label" in dataset.coords
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_bounds_of_cell_crossing_zero_keep_width(dataset: xr.Dataset) -> None:
    lon = dataset["lon"].variable
    dataset = dataset.assign_coords(lon=lon.copy(data=lon.data - 45.0))
    dataset["lon_bnds"] -= 45.0

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)

    np.testing.assert_array_equal(dataset["lon"], [0, 90, 180, 270])
    np.testing.assert_array_equal(
        dataset["lon_bnds"], [[-45, 45], [45, 135], [135, 225], [225, 315]]
    )
