import warnings

import pytest
import woodpecker
from woodpecker.io.backends.xr import XarrayInput

from .esa_cci_data import CASES, CHUNKS, KERCHUNK_TIME_STEPS, Case

xcube_store = pytest.importorskip("xcube.core.store")
iris = pytest.importorskip("iris")
iris_conversion = pytest.importorskip("tests.integration.iris_conversion")

# The other tests open the zarr and Kerchunk datasets without xcube-cci, so
# check that they also work when opened with the xcube-cci data stores. The
# Kerchunk store has no option to set the chunks, so the datasets are
# rechunked, and like in the other tests, only the first time steps of the
# Kerchunk datasets are used, unless pytest runs with --full-time-axis.
XCUBE_CASES = [case for case in CASES if case.store != "cciodp"]


@pytest.mark.parametrize("case", XCUBE_CASES, ids=[c.id for c in XCUBE_CASES])
def test_loads_with_iris_without_warnings(
    case: Case,
    full_time_axis: bool,  # noqa: FBT001
) -> None:
    store = xcube_store.new_data_store(case.store)
    dataset = store.open_data(case.data_id)
    if case.store == "ccikc" and not full_time_axis:
        dataset = dataset.isel(time=slice(KERCHUNK_TIME_STEPS))
    dataset = dataset.chunk(CHUNKS)
    # Woodpecker selects the recipe by matching its path_patterns against
    # the data id.
    woodpecker.recipe.apply(
        XarrayInput(payload=dataset, name=case.data_id),
        woodpecker.recipe.catalog(),
        dry_run=False,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cubes = iris_conversion.dataset_to_cubes(dataset)

    assert len(cubes) == 1
    cube = cubes[0]
    assert cube.var_name == case.variable_id
    # Iris splits "area: mean where sea time: mean" in two cell methods.
    assert " ".join(str(m) for m in cube.cell_methods) in (
        "area: time: mean",
        "area: mean where sea time: mean",
    )
    if case.variable_id == "prw":
        coord_system = cube.coord_system()
        assert isinstance(coord_system, iris.coord_systems.GeogCS)
        assert coord_system.datum == "WGS84"
