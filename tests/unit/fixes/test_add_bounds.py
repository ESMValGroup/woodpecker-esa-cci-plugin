from collections.abc import Callable

import numpy as np
import pytest
import woodpecker
import xarray as xr
from pyproj import CRS, Transformer
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.add_bounds"
OPTIONS = {FIX_ID: {"coordinates": ["lat", "lon"]}}
POLAR_OPTIONS = {
    FIX_ID: {
        "coordinates": ["lat", "lon"],
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
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    """Remove the latitude and longitude bounds, like in the SST dataset."""
    for name in ("lat", "lon"):
        del tcwv_dataset[name].attrs["bounds"]
    return tcwv_dataset.drop_vars(["lat_bnds", "lon_bnds"])


@pytest.fixture
def polar_dataset() -> xr.Dataset:
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


def test_bounds_are_added(
    dataset: xr.Dataset, tcwv_dataset: xr.Dataset
) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["lat has no bounds", "lon has no bounds"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "lat_bnds" not in dataset

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    for name in ("lat", "lon"):
        bounds = dataset[name].attrs["bounds"]
        assert bounds == f"{name}_bnds"
        assert dataset[bounds].dims == (name, "bnds")
        # The synthetic dataset has the bounds of the real dataset.
        np.testing.assert_allclose(dataset[bounds], tcwv_dataset[bounds])
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_existing_bounds_are_kept(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    ("coordinate", "match"),
    [
        ("latitude", "latitude: it does not exist"),
        ("time_bnds", "time_bnds: a 2-D coordinate needs the grid_mapping"),
        ("tcwv", "tcwv: it is not a dimension coordinate or a 2-D coordinate"),
        ("lat", "lat: its step size is not fixed"),
    ],
)
def test_invalid_coordinate_raises(
    dataset: xr.Dataset,
    coordinate: str,
    match: str,
) -> None:
    lat = dataset["lat"].to_numpy().copy()
    lat[-1] += 1.0
    dataset["lat"] = dataset["lat"].copy(data=lat)
    options = {FIX_ID: {"coordinates": [coordinate]}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_single_value_raises(dataset: xr.Dataset) -> None:
    dataset = dataset.isel(lat=slice(0, 1))

    with pytest.raises(ValueError, match="lat: it has less than 2 values"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_existing_bounds_variable_raises(dataset: xr.Dataset) -> None:
    dataset["lat_bnds"] = dataset["lat"]

    with pytest.raises(ValueError, match="lat: lat_bnds already exists"):
        woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_bounds_of_varying_step_are_halfway() -> None:
    # Like the latitudes of an EASE-Grid 2.0.
    dataset = xr.Dataset(coords={"lat": ("lat", [-1.0, 0.0, 2.0, 5.0])})
    options = {FIX_ID: {"coordinates": ["lat"], "varying_step": ["lat"]}}

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=options)
    np.testing.assert_array_equal(
        dataset["lat_bnds"],
        [[-1.5, -0.5], [-0.5, 1.0], [1.0, 3.5], [3.5, 6.5]],
    )
    assert dataset["lat"].attrs["bounds"] == "lat_bnds"


def test_geographic_bounds_are_added(polar_dataset: xr.Dataset) -> None:
    original = polar_dataset.copy(deep=True)

    findings = woodpecker.check(
        polar_dataset, fixes=FIX_ID, options=POLAR_OPTIONS
    )
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["lat has no bounds", "lon has no bounds"]

    preview = woodpecker.apply(
        polar_dataset, fixes=FIX_ID, dry_run=True, options=POLAR_OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_equal(polar_dataset, original)

    result = woodpecker.apply(
        polar_dataset, fixes=FIX_ID, dry_run=False, options=POLAR_OPTIONS
    )
    assert result.changed == 1
    for name in ("lat", "lon"):
        assert polar_dataset[name].attrs["bounds"] == f"{name}_bnds"
        assert polar_dataset[f"{name}_bnds"].dims == ("yc", "xc", "vertices")
    # The cell in the first row and column, at the top left of the grid,
    # with its vertices anticlockwise from the bottom left.
    x = np.array([-2.0, -1.0, -1.0, -2.0]) * STEP
    y = np.array([1.0, 1.0, 2.0, 2.0]) * STEP
    lon, lat = _transformer().transform(x, y)
    np.testing.assert_allclose(polar_dataset["lat_bnds"][0, 0], lat)
    np.testing.assert_allclose(polar_dataset["lon_bnds"][0, 0], lon)
    # The cells around the pole have a vertex at the pole.
    np.testing.assert_allclose(polar_dataset["lat_bnds"][1, 1, 1], 90.0)
    assert not woodpecker.check(
        polar_dataset, fixes=FIX_ID, options=POLAR_OPTIONS
    )


def test_bounds_across_antimeridian_are_near_the_center(
    polar_dataset: xr.Dataset,
) -> None:
    woodpecker.apply(
        polar_dataset, fixes=FIX_ID, dry_run=False, options=POLAR_OPTIONS
    )

    # The cells along x = 0 on the side of the antimeridian, where pyproj
    # returns longitudes of 180 and -180 for the vertices, without the cells
    # with a vertex at the pole, where the longitude is undefined.
    lon = polar_dataset["lon"][0, 1:3].to_numpy()
    lon_bnds = polar_dataset["lon_bnds"][0, 1:3].to_numpy()
    assert (np.abs(lon_bnds - lon[..., np.newaxis]) <= 90).all()


def test_existing_geographic_bounds_are_kept(
    polar_dataset: xr.Dataset,
) -> None:
    woodpecker.apply(
        polar_dataset, fixes=FIX_ID, dry_run=False, options=POLAR_OPTIONS
    )
    del polar_dataset["lon"].attrs["bounds"]
    polar_dataset = polar_dataset.drop_vars("lon_bnds")
    lat_bnds = polar_dataset["lat_bnds"].copy()

    findings = woodpecker.check(
        polar_dataset, fixes=FIX_ID, options=POLAR_OPTIONS
    )
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["lon has no bounds"]

    woodpecker.apply(
        polar_dataset, fixes=FIX_ID, dry_run=False, options=POLAR_OPTIONS
    )
    xr.testing.assert_identical(
        polar_dataset["lat_bnds"].variable, lat_bnds.variable
    )
    assert "lon_bnds" in polar_dataset


# Changes that make the polar_dataset invalid, and the errors they raise.
INVALID: dict[str, tuple[Callable[[xr.Dataset], xr.Dataset], str]] = {
    "no_grid_mapping": (
        lambda ds: ds.drop_vars("Lambert_Azimuthal_Grid"),
        "Lambert_Azimuthal_Grid does not exist",
    ),
    "not_2d": (
        lambda ds: ds.isel(xc=0),
        "lat: it is not a dimension coordinate or a 2-D coordinate",
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
    "latitude_units": (
        lambda ds: ds.assign_coords(lat=ds["lat"].assign_attrs(units="m")),
        "lat: its units, m, are not those of a latitude or longitude",
    ),
}


@pytest.mark.parametrize("invalid", INVALID)
def test_invalid_polar_dataset_raises(
    polar_dataset: xr.Dataset, invalid: str
) -> None:
    change, match = INVALID[invalid]
    polar_dataset = change(polar_dataset)

    with pytest.raises(ValueError, match=match):
        woodpecker.check(polar_dataset, fixes=FIX_ID, options=POLAR_OPTIONS)


def test_projection_bounds_are_added_in_the_same_step(
    polar_dataset: xr.Dataset,
) -> None:
    expected = polar_dataset.copy(deep=True)
    woodpecker.apply(
        expected, fixes=FIX_ID, dry_run=False, options=POLAR_OPTIONS
    )
    for name in ("xc", "yc"):
        del polar_dataset[name].attrs["bounds"]
    polar_dataset = polar_dataset.drop_vars(["xc_bnds", "yc_bnds"])
    options = {
        FIX_ID: {
            "coordinates": ["lat", "lon", "xc", "yc"],
            "grid_mapping": "Lambert_Azimuthal_Grid",
        },
    }

    findings = woodpecker.check(polar_dataset, fixes=FIX_ID, options=options)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        "lat has no bounds",
        "lon has no bounds",
        "xc has no bounds",
        "yc has no bounds",
    ]

    woodpecker.apply(
        polar_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    np.testing.assert_allclose(polar_dataset["lat_bnds"], expected["lat_bnds"])
    np.testing.assert_allclose(polar_dataset["lon_bnds"], expected["lon_bnds"])
    assert polar_dataset["xc"].attrs["bounds"] == "xc_bnds"
    assert polar_dataset["yc"].attrs["bounds"] == "yc_bnds"
    assert not woodpecker.check(polar_dataset, fixes=FIX_ID, options=options)
