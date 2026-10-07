"""Convert xarray datasets to iris cubes for the tests."""

from typing import Any

import pytest
import xarray as xr

iris = pytest.importorskip("iris")
ncdata_xarray = pytest.importorskip("ncdata.xarray")
dataset_like = pytest.importorskip("ncdata.dataset_like")


def dataset_to_cubes(dataset: xr.Dataset) -> Any:  # noqa: ANN401
    """Convert ``dataset`` to an iris cube list.

    This is equivalent to writing ``dataset`` to a netCDF file and loading
    that with iris, but the data is not copied or computed. Unlike
    ``ncdata.iris_xarray.cubes_from_xarray``, it uses ``iris.load_raw``,
    which is faster because it does not try to merge the cubes.
    """
    ncdata = ncdata_xarray.from_xarray(dataset)
    # Opt in to loading the datum from the grid mapping, otherwise iris
    # warns that it ignores it.
    with iris.FUTURE.context(datum_support=True):
        return iris.load_raw(dataset_like.Nc4DatasetLike(ncdata))
