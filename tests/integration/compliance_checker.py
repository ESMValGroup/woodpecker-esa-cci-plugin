"""Run the IOOS compliance checker on recipe output for the tests."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import xarray as xr

from tests.integration.esa_cci_data import TIME_STEPS

netcdf4 = pytest.importorskip("netCDF4")
suite = pytest.importorskip("compliance_checker.suite")


# The regions of the subsets of the polar grids, with land and sea, as
# latitude and longitude ranges: Svalbard and the coast of Dronning Maud
# Land in Antarctica.
POLAR_REGIONS = {
    "north": ((76.0, 80.0), (10.0, 20.0)),
    "south": ((-71.0, -68.0), (0.0, 10.0)),
}


def _polar_subset(dataset: xr.Dataset) -> xr.Dataset:
    """Return the cells of ``dataset`` around a polar coast.

    The latitudes and longitudes of polar grids are 2-D, so this selects
    the smallest rectangle of cells that contains the region.
    """
    lat = dataset["lat"].to_numpy()
    lon = dataset["lon"].to_numpy()
    hemisphere = "north" if np.nanmax(lat) > 0 else "south"
    (lat_min, lat_max), (lon_min, lon_max) = POLAR_REGIONS[hemisphere]
    inside = (
        (lat >= lat_min)
        & (lat <= lat_max)
        & (lon >= lon_min)
        & (lon <= lon_max)
    )
    rows, columns = np.nonzero(inside)
    y, x = dataset["lat"].dims
    return dataset.isel(
        {
            y: slice(rows.min(), rows.max() + 1),
            x: slice(columns.min(), columns.max() + 1),
        }
    )


def write_subset(dataset: xr.Dataset, path: Path) -> None:
    """Write a small part of ``dataset`` to the netCDF file ``path``.

    The compliance checker only reads netCDF files, so this writes the first
    time steps around the Dutch coast, or a polar coast for polar grids, to
    cover both land and sea.
    """
    subset = dataset.isel(time=slice(TIME_STEPS))
    if subset["lat"].ndim == 2:
        subset = _polar_subset(subset)
    else:
        subset = subset.sel(lat=slice(51.5, 53.0), lon=slice(3.0, 6.0))
    assert all(size > 1 for size in subset.sizes.values())
    # Coordinates cannot have missing values, but xarray writes a _FillValue
    # for floating point variables, unless the encoding says otherwise.
    for name in list(subset.coords):
        for var in (name, subset[name].attrs.get("bounds")):
            if var in subset.variables:
                subset[var].encoding["_FillValue"] = None
    subset.to_netcdf(path)


def run_checker(
    path: Path,
    name: str,
    checker: type[Any],
    options: dict[str, Any] | None = None,
) -> list[str]:
    """Return the failure messages of ``checker`` for the file ``path``.

    The ``name`` includes the version, e.g. ``cf:1.11``.
    """
    # The options are keyed by the name without version.
    check_suite = suite.CheckSuite(
        options={name.split(":", maxsplit=1)[0]: options or {}}
    )
    # Only load this checker, the other checkers include deprecated ones.
    check_suite.checkers = {name: checker}
    with netcdf4.Dataset(path) as ds:
        results = check_suite.run_all(ds, [name])
    groups, exceptions = results[name]
    assert not exceptions

    report = check_suite.build_structure(name, groups, str(path))
    return [
        f"{result.name}: {message}"
        for priority in ("high", "medium", "low")
        for result in report[f"{priority}_priorities"]
        if result.value[0] < result.value[1]
        for message in result.msgs
    ]
