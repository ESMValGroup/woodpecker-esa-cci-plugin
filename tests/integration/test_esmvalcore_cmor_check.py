import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

# Importing the configuration loads the CMOR tables.
pytest.importorskip("esmvalcore.config")
esmvalcore_check = pytest.importorskip("esmvalcore.cmor.check")
pytest.importorskip("s3fs")
iris_xarray = pytest.importorskip("ncdata.iris_xarray")
iris = pytest.importorskip("iris")


@pytest.mark.parametrize("case", CASES, ids=[c.variable_id for c in CASES])
def test_passes_cmip7_cmor_check(case: Case) -> None:
    dataset = open_fixed_dataset(case)

    with iris.FUTURE.context(datum_support=True):
        cubes = iris_xarray.cubes_from_xarray(dataset)
    cube = cubes.extract_cube(case.standard_name)
    # Iris changes the latitude and longitude units to degrees, so restore
    # them from the dataset like the ESMValCore loader does.
    for coord in cube.coords(axis="X") + cube.coords(axis="Y"):
        coord.units = dataset[coord.var_name].attrs["units"]

    esmvalcore_check.cmor_check(
        cube,
        cmor_table="CMIP7",
        mip=case.realm,
        short_name=case.variable_id,
        branding_suffix=case.variable_branding_suffix,
        frequency=case.frequency,
    )
