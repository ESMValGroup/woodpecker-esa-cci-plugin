import dask.array as da
import numpy as np
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.remove_xcube_cci_odp_dimensions"


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


def test_other_stores_are_not_changed(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_added_dimensions_are_removed() -> None:
    dataset = _dataset()
    original = dataset.copy(deep=True)

    findings = woodpecker.check(dataset, fixes=FIX_ID)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        "lat has dimensions time, which it does not have in the original files"
    ]

    preview = woodpecker.apply(dataset, fixes=FIX_ID, dry_run=True)
    assert preview.changed == 1
    xr.testing.assert_equal(dataset, original)

    result = woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False)
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
    assert not woodpecker.check(dataset, fixes=FIX_ID)
