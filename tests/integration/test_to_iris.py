import warnings

import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

pytest.importorskip("s3fs")
iris_xarray = pytest.importorskip("ncdata.iris_xarray")
iris = pytest.importorskip("iris")


@pytest.mark.parametrize("case", CASES, ids=[c.short_name for c in CASES])
def test_loads_with_iris_without_warnings(case: Case) -> None:
    dataset = open_fixed_dataset(case)

    # Opt in to loading the datum from the grid mapping, otherwise iris
    # warns that it ignores it.
    with (
        iris.FUTURE.context(datum_support=True),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("error")
        cubes = iris_xarray.cubes_from_xarray(dataset)

    assert len(cubes) == 1
    for cube in cubes:
        assert cube.var_name == case.short_name
        assert cube.standard_name == case.standard_name
