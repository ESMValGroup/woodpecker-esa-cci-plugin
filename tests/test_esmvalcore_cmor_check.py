import json
from typing import NamedTuple

import pytest
import woodpecker
import xarray as xr

# Importing the configuration loads the CMOR tables.
pytest.importorskip("esmvalcore.config")
esmvalcore_check = pytest.importorskip("esmvalcore.cmor.check")
s3fs = pytest.importorskip("s3fs")
iris_xarray = pytest.importorskip("ncdata.iris_xarray")
iris = pytest.importorskip("iris")

pytestmark = pytest.mark.integration

# The ESA CCI zarr store, as used by the xcube-cci "ccizarr" data store.
BUCKET = "esacci"
STORAGE_OPTIONS = {
    "anon": True,
    "client_kwargs": {"endpoint_url": "https://cci-ke-o.s3-ext.jc.rl.ac.uk"},
}


class Case(NamedTuple):
    """A dataset, the recipe for it and the CMIP7 variable it provides."""

    data_id: str
    recipe_id: str
    standard_name: str
    mip: str
    short_name: str
    branding_suffix: str
    frequency: str


CASES = [
    Case(
        "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr",
        "esa_cci.water_vapour",
        "atmosphere_mass_content_of_water_vapor",
        "atmos",
        "prw",
        "tavg-u-hxy-u",
        "mon",
    ),
    Case(
        "ESACCI-L4_GHRSST-SST-GMPE-GLOB_CDR2.0-1981-2016-v02.0-fv01.0.zarr",
        "esa_cci.sea_surface_temperature",
        "sea_surface_temperature",
        "ocean",
        "tos",
        "tavg-u-hxy-sea",
        "day",
    ),
]
# Parts of the data ids of the datasets that the recipes cover.
PATTERNS = ("-WATERVAPOUR-", "-SST-")


def test_all_datasets_are_checked() -> None:
    fs = s3fs.S3FileSystem(**STORAGE_OPTIONS)
    data_ids = json.loads(fs.cat(f"{BUCKET}/data_ids.json"))
    expected = [i for i in data_ids if any(p in i for p in PATTERNS)]
    assert sorted(expected) == sorted(case.data_id for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.short_name for c in CASES])
def test_passes_cmip7_cmor_check(case: Case) -> None:
    dataset = xr.open_zarr(
        f"s3://{BUCKET}/{case.data_id}",
        storage_options=STORAGE_OPTIONS,
    )
    recipe = woodpecker.recipe.get(case.recipe_id)
    woodpecker.recipe.apply(dataset, recipe, dry_run=False)

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
        mip=case.mip,
        short_name=case.short_name,
        branding_suffix=case.branding_suffix,
        frequency=case.frequency,
    )
