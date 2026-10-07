import warnings

import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

pytest.importorskip("s3fs")
iris_conversion = pytest.importorskip("tests.integration.iris_conversion")


@pytest.mark.parametrize("case", CASES, ids=[c.variable_id for c in CASES])
def test_loads_with_iris_without_warnings(case: Case) -> None:
    dataset = open_fixed_dataset(case)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cubes = iris_conversion.dataset_to_cubes(dataset)

    assert len(cubes) == 1
    for cube in cubes:
        assert cube.var_name == case.variable_id
