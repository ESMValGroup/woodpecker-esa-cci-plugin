"""ESA CCI datasets from the ESA CCI Open Data Portal for the tests."""

from typing import NamedTuple

import woodpecker
import xarray as xr
from woodpecker.io.backends.xr import XarrayInput

# The ESA CCI zarr store, as used by the xcube-cci "ccizarr" data store.
BUCKET = "esacci"
STORAGE_OPTIONS = {
    "anon": True,
    "client_kwargs": {"endpoint_url": "https://cci-ke-o.s3-ext.jc.rl.ac.uk"},
}


class Case(NamedTuple):
    """A dataset and the CMIP7 variable its recipe provides."""

    data_id: str
    standard_name: str
    realm: str
    variable_id: str
    variable_branding_suffix: str
    frequency: str


CASES = [
    Case(
        "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr",
        "atmosphere_mass_content_of_water_vapor",
        "atmos",
        "prw",
        "tavg-u-hxy-u",
        "mon",
    ),
    Case(
        "ESACCI-L4_GHRSST-SST-GMPE-GLOB_CDR2.0-1981-2016-v02.0-fv01.0.zarr",
        "sea_surface_temperature",
        "ocean",
        "tos",
        "tavg-u-hxy-sea",
        "day",
    ),
]


def open_fixed_dataset(case: Case) -> xr.Dataset:
    """Open the dataset of ``case`` lazily and apply the recipe matching it.

    Woodpecker selects the recipe by matching the recipe ``path_patterns``
    against the data id, so the data id is passed as the input name.
    """
    dataset: xr.Dataset = xr.open_zarr(
        f"s3://{BUCKET}/{case.data_id}",
        storage_options=STORAGE_OPTIONS,
    )
    woodpecker.recipe.apply(
        XarrayInput(payload=dataset, name=case.data_id),
        woodpecker.recipe.catalog(),
        dry_run=False,
    )
    return dataset
