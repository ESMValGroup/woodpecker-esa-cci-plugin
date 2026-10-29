from collections.abc import Callable

import numpy as np
import pytest
import woodpecker
import xarray as xr
from pyproj import CRS, Transformer
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.add_geographic_bounds"
OPTIONS = {
    FIX_ID: {
        "latitude": "lat",
        "longitude": "lon",
        "grid_mapping": "Lambert_Azimuthal_Grid",
    },
}
# The grid mapping of the northern hemisphere sea ice datasets.
GRID_MAPPING = {
    "grid_mapping_name": "lambert_azimuthal_equal_area",
    "longitude_of_projection_origin": 0.0,
    "latitude_of_projection_origin": 90.0,
    "false_easting": 0.0,
    "false_northing": 0.0,
    "semi_major_axis": 6378137.0,
    "inverse_flattening": 298.257223563,
}
# The cell size in m.
STEP = 1000e3


def _transformer() -> Transformer:
    crs = CRS.from_cf(GRID_MAPPING)
    return Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)


@pytest.fixture
def dataset() -> xr.Dataset:
    """Return a polar grid like that of the sea ice datasets.

    The y coordinate decreases, and the pole is at the corner of 4 cells.
    """
    xc = np.arange(-1.5, 2.0) * STEP
    yc = -xc
    lon, lat = _transformer().transform(*np.meshgrid(xc, yc))
    return xr.Dataset(
        {
            "ice_conc": (("yc", "xc"), np.ones((4, 4))),
            "Lambert_Azimuthal_Grid": ((), 0, GRID_MAPPING),
            "xc_bnds": (
                ("xc", "bnds"),
                np.column_stack([xc - STEP / 2, xc + STEP / 2]),
            ),
            "yc_bnds": (
                ("yc", "bnds"),
                np.column_stack([yc + STEP / 2, yc - STEP / 2]),
            ),
        },
        coords={
            "xc": (
                "xc",
                xc,
                {
                    "standard_name": "projection_x_coordinate",
                    "units": "m",
                    "bounds": "xc_bnds",
                },
            ),
            "yc": (
                "yc",
                yc,
                {
                    "standard_name": "projection_y_coordinate",
                    "units": "m",
                    "bounds": "yc_bnds",
                },
            ),
            "lat": (("yc", "xc"), lat, {"units": "degrees_north"}),
            "lon": (("yc", "xc"), lon, {"units": "degrees_east"}),
        },
    )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_bounds_are_added(dataset: xr.Dataset) -> None:
    original = dataset.copy(deep=True)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["lat has no bounds", "lon has no bounds"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_equal(dataset, original)

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    for name in ("lat", "lon"):
        assert dataset[name].attrs["bounds"] == f"{name}_bnds"
        assert dataset[f"{name}_bnds"].dims == ("yc", "xc", "vertices")
    # The cell in the first row and column, at the top left of the grid,
    # with its vertices anticlockwise from the bottom left.
    x = np.array([-2.0, -1.0, -1.0, -2.0]) * STEP
    y = np.array([1.0, 1.0, 2.0, 2.0]) * STEP
    lon, lat = _transformer().transform(x, y)
    np.testing.assert_allclose(dataset["lat_bnds"][0, 0], lat)
    np.testing.assert_allclose(dataset["lon_bnds"][0, 0], lon)
    # The cells around the pole have a vertex at the pole.
    np.testing.assert_allclose(dataset["lat_bnds"][1, 1, 1], 90.0)
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_bounds_across_antimeridian_are_near_the_center(
    dataset: xr.Dataset,
) -> None:
    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)

    # The cells along x = 0 on the side of the antimeridian, where pyproj
    # returns longitudes of 180 and -180 for the vertices, without the cells
    # with a vertex at the pole, where the longitude is undefined.
    lon = dataset["lon"][0, 1:3].to_numpy()
    lon_bnds = dataset["lon_bnds"][0, 1:3].to_numpy()
    assert (np.abs(lon_bnds - lon[..., np.newaxis]) <= 90).all()


def test_existing_bounds_are_kept(dataset: xr.Dataset) -> None:
    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    del dataset["lon"].attrs["bounds"]
    dataset = dataset.drop_vars("lon_bnds")
    lat_bnds = dataset["lat_bnds"].copy()

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["lon has no bounds"]

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    xr.testing.assert_identical(
        dataset["lat_bnds"].variable, lat_bnds.variable
    )
    assert "lon_bnds" in dataset


# Changes that make the dataset invalid, and the errors they raise.
INVALID: dict[str, tuple[Callable[[xr.Dataset], xr.Dataset], str]] = {
    "no_grid_mapping": (
        lambda ds: ds.drop_vars("Lambert_Azimuthal_Grid"),
        "Lambert_Azimuthal_Grid does not exist",
    ),
    "not_2d": (
        lambda ds: ds.isel(xc=0),
        "lat and lon: they are not 2-D coordinates",
    ),
    "bounds_variable_exists": (
        lambda ds: ds.assign({"lat_bnds": ds["lat"]}),
        "lat: lat_bnds already exists",
    ),
    "no_projection_coordinate": (
        lambda ds: ds.assign_coords(
            xc=ds["xc"].assign_attrs(standard_name="longitude")
        ),
        "none of its dimensions is a projection_x_coordinate",
    ),
    "units": (
        lambda ds: ds.assign_coords(xc=ds["xc"].assign_attrs(units="km")),
        "xc is not in m",
    ),
    "no_projection_bounds": (
        lambda ds: ds.drop_vars("yc_bnds"),
        "yc has no bounds",
    ),
}


@pytest.mark.parametrize("invalid", INVALID)
def test_invalid_dataset_raises(dataset: xr.Dataset, invalid: str) -> None:
    change, match = INVALID[invalid]
    dataset = change(dataset)

    with pytest.raises(ValueError, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_incomplete_options_raise() -> None:
    fix = FixFunctionRegistry.instantiate(FIX_ID)

    with pytest.raises(ValueError, match="must all be set"):
        fix.configure({"latitude": "lat"})
