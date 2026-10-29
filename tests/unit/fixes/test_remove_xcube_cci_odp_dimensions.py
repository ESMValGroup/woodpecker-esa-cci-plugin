import dask.array as da
import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.remove_xcube_cci_odp_dimensions"
TIME = {FIX_ID: {"dimensions": ["time"]}}
LON = {FIX_ID: {"dimensions": ["lon"]}}


def _dataset() -> xr.Dataset:
    """Return a dataset like the sea ice datasets in the Open Data Portal.

    The store repeats the 2-D latitudes of the files for each time step.
    """
    lat = np.array([[80.0, 85.0], [85.0, 80.0]], dtype="float32")
    return xr.Dataset(
        {
            "ice_conc": (
                ("time", "yc", "xc"),
                np.ones((3, 2, 2)),
                {"file_dimensions": ["time", "yc", "xc"]},
            ),
        },
        coords={
            "lat": (
                ("time", "yc", "xc"),
                np.stack([lat] * 3),
                {"units": "degrees_north", "file_dimensions": ["yc", "xc"]},
            ),
            "time": ("time", np.arange(3.0), {"file_dimensions": "time"}),
        },
    ).chunk({"time": 1})


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def _zonal_mean() -> xr.Dataset:
    """Return a dataset like the ozone zonal means in the Open Data Portal.

    The files store each month in a file with a time dimension, the store
    names the latitudes lat, and repeats the values along a lon dimension
    that it adds.
    """
    return xr.Dataset(
        {
            "ozone_mixing_ratio": (
                ("time", "air_pressure", "lat", "lon"),
                np.ones((2, 3, 2, 4)),
                {
                    "file_dimensions": [
                        "time",
                        "air_pressure",
                        "latitude_centers",
                    ]
                },
            ),
        },
        coords={
            "lat": ("lat", [-5.0, 5.0]),
            "lon": ("lon", [-135.0, -45.0, 45.0, 135.0]),
        },
    ).chunk({"time": 1})


def test_other_stores_are_not_changed(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=TIME)


def test_without_dimensions_nothing_changes() -> None:
    assert not woodpecker.check(_dataset(), fixes=FIX_ID)


def test_added_dimensions_are_removed() -> None:
    dataset = _dataset()
    original = dataset.copy(deep=True)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=TIME)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        "lat has dimensions time, which it does not have in the original files"
    ]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, options=TIME, dry_run=True
    )
    assert preview.changed == 1
    xr.testing.assert_equal(dataset, original)

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, options=TIME, dry_run=False
    )
    assert result.changed == 1
    lat = dataset["lat"]
    assert lat.dims == ("yc", "xc")
    assert "lat" in dataset.coords
    # Only the first time step is read.
    assert isinstance(lat.data, da.Array)
    np.testing.assert_array_equal(lat, original["lat"][0])
    assert lat.attrs == original["lat"].attrs
    xr.testing.assert_identical(
        dataset["ice_conc"].variable, original["ice_conc"].variable
    )
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=TIME)


def test_only_configured_dimensions_are_removed() -> None:
    """Data stored in a file per time step keep their time dimension."""
    dataset = _dataset()
    dataset["ice_conc"].attrs["file_dimensions"] = ["yc", "xc"]

    woodpecker.apply(dataset, fixes=FIX_ID, options=TIME, dry_run=False)

    assert dataset["ice_conc"].dims == ("yc", "xc")
    dataset = _dataset()
    dataset["ice_conc"].attrs["file_dimensions"] = ["yc", "xc"]
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=LON)


@pytest.mark.parametrize(
    "file_dimensions",
    [["time", "latitude", "longitude"], ["time", "lat", "lon"]],
)
def test_renamed_dimensions_are_kept(file_dimensions: list[str]) -> None:
    dataset = _zonal_mean()
    dataset["ozone_mixing_ratio"].attrs["file_dimensions"] = [
        "air_pressure",
        *file_dimensions,
    ]
    assert not woodpecker.check(
        dataset,
        fixes=FIX_ID,
        options={FIX_ID: {"dimensions": ["lat", "lon", "time"]}},
    )


def test_added_longitude_of_zonal_means_is_removed() -> None:
    dataset = _zonal_mean()
    original = dataset.copy(deep=True)

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, options=LON, dry_run=False
    )

    assert result.changed == 1
    o3 = dataset["ozone_mixing_ratio"]
    assert o3.dims == ("time", "air_pressure", "lat")
    np.testing.assert_array_equal(
        o3, original["ozone_mixing_ratio"].isel(lon=0)
    )
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=LON)
