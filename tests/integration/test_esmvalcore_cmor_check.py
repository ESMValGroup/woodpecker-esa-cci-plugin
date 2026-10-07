import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

# Importing the configuration loads the CMOR tables.
pytest.importorskip("esmvalcore.config")
esmvalcore_check = pytest.importorskip("esmvalcore.cmor.check")
pytest.importorskip("s3fs")
iris_conversion = pytest.importorskip("tests.integration.iris_conversion")


@pytest.mark.parametrize("case", CASES, ids=[c.variable_id for c in CASES])
def test_passes_cmip7_cmor_check(case: Case) -> None:
    dataset = open_fixed_dataset(case)

    cubes = iris_conversion.dataset_to_cubes(dataset)
    assert len(cubes) == 1
    cube = cubes[0]
    assert cube.var_name == case.variable_id
    # Iris changes the latitude and longitude units to degrees, so restore
    # them from the dataset like the ESMValCore loader does.
    for coord in cube.coords(axis="X") + cube.coords(axis="Y"):
        coord.units = dataset[coord.var_name].attrs["units"]

    # The recipe stores the CMIP7 variable in the global attributes.
    attrs = cube.attributes
    esmvalcore_check.cmor_check(
        cube,
        cmor_table="CMIP7",
        mip=attrs["realm"],
        short_name=attrs["variable_id"],
        branding_suffix=attrs["branded_variable"].removeprefix(
            f"{attrs['variable_id']}_"
        ),
        frequency=attrs["frequency"],
    )
