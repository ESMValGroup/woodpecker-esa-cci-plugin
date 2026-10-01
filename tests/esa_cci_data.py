"""ESA CCI datasets from the ESA CCI Open Data Portal for the tests."""

from typing import NamedTuple

import woodpecker
import xarray as xr

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


def open_fixed_dataset(case: Case) -> xr.Dataset:
    """Open the dataset of ``case`` lazily and apply its recipe."""
    dataset: xr.Dataset = xr.open_zarr(
        f"s3://{BUCKET}/{case.data_id}",
        storage_options=STORAGE_OPTIONS,
    )
    recipe = woodpecker.recipe.get(case.recipe_id)
    woodpecker.recipe.apply(dataset, recipe, dry_run=False)
    return dataset
