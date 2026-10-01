import warnings
from typing import Any

import pytest
import woodpecker

xcube_store = pytest.importorskip("xcube.core.store")
iris_xarray = pytest.importorskip("ncdata.iris_xarray")
iris = pytest.importorskip("iris")

pytestmark = pytest.mark.integration

DATA_ID = "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr"
RECIPE_ID = "esa_cci.water_vapour"


@pytest.fixture(scope="module")
def cci_store() -> Any:  # noqa: ANN401
    return xcube_store.new_data_store("ccizarr")


def test_prw_loads_with_iris_without_warnings(cci_store: Any) -> None:  # noqa: ANN401
    dataset = cci_store.open_data(DATA_ID)
    recipe = woodpecker.recipe.get(RECIPE_ID)
    woodpecker.recipe.apply(dataset, recipe, dry_run=False)

    # Opt in to loading the datum from the grid mapping, otherwise iris
    # warns that it ignores it.
    with (
        iris.FUTURE.context(datum_support=True),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("error")
        cubes = iris_xarray.cubes_from_xarray(dataset)

    cube = cubes.extract_cube("atmosphere_mass_content_of_water_vapor")
    assert cube.var_name == "prw"
    assert cube.long_name == "Water Vapor Path"
    assert cube.units == "kg m-2"
    assert [str(m) for m in cube.cell_methods] == ["area: time: mean"]
    coord_system = cube.coord_system()
    assert isinstance(coord_system, iris.coord_systems.GeogCS)
    assert coord_system.datum == "WGS84"
