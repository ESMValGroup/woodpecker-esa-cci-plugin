import warnings
from typing import Any

import pytest
import woodpecker
from woodpecker.io.backends.xr import XarrayInput

xcube_store = pytest.importorskip("xcube.core.store")
iris = pytest.importorskip("iris")
iris_conversion = pytest.importorskip("tests.integration.iris_conversion")

DATA_ID = "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr"


@pytest.fixture(scope="module")
def cci_store() -> Any:  # noqa: ANN401
    return xcube_store.new_data_store("ccizarr")


def test_prw_loads_with_iris_without_warnings(cci_store: Any) -> None:  # noqa: ANN401
    dataset = cci_store.open_data(DATA_ID)
    # Woodpecker selects the recipe by matching its path_patterns against
    # the data id.
    woodpecker.recipe.apply(
        XarrayInput(payload=dataset, name=DATA_ID),
        woodpecker.recipe.catalog(),
        dry_run=False,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cubes = iris_conversion.dataset_to_cubes(dataset)

    cube = cubes.extract_cube("atmosphere_mass_content_of_water_vapor")
    assert cube.var_name == "prw"
    assert cube.long_name == "Water Vapor Path"
    assert cube.units == "kg m-2"
    assert [str(m) for m in cube.cell_methods] == ["area: time: mean"]
    coord_system = cube.coord_system()
    assert isinstance(coord_system, iris.coord_systems.GeogCS)
    assert coord_system.datum == "WGS84"
