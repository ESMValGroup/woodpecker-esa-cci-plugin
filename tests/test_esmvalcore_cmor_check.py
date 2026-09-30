import pytest
import woodpecker
import xarray as xr

# Importing the configuration loads the CMOR tables.
pytest.importorskip("esmvalcore.config")
esmvalcore_check = pytest.importorskip("esmvalcore.cmor.check")
pytest.importorskip("s3fs")
iris_xarray = pytest.importorskip("ncdata.iris_xarray")
iris = pytest.importorskip("iris")

pytestmark = pytest.mark.integration

# The ESA CCI zarr store, as used by the xcube-cci "ccizarr" data store.
DATA_URL = (
    "s3://esacci/ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr"
)
STORAGE_OPTIONS = {
    "anon": True,
    "client_kwargs": {"endpoint_url": "https://cci-ke-o.s3-ext.jc.rl.ac.uk"},
}
RECIPE_ID = "esa_cci.water_vapour"


def test_prw_passes_cmip7_cmor_check() -> None:
    dataset = xr.open_zarr(DATA_URL, storage_options=STORAGE_OPTIONS)
    recipe = woodpecker.recipe.get(RECIPE_ID)
    woodpecker.recipe.apply(dataset, recipe, dry_run=False)

    with iris.FUTURE.context(datum_support=True):
        cubes = iris_xarray.cubes_from_xarray(dataset)
    cube = cubes.extract_cube("atmosphere_mass_content_of_water_vapor")
    # Iris changes the latitude and longitude units to degrees, so restore
    # them from the dataset like the ESMValCore loader does.
    for coord in cube.coords(axis="X") + cube.coords(axis="Y"):
        coord.units = dataset[coord.var_name].attrs["units"]

    esmvalcore_check.cmor_check(
        cube,
        cmor_table="CMIP7",
        mip="atmos",
        short_name="prw",
        branding_suffix="tavg-u-hxy-u",
        frequency="mon",
    )
