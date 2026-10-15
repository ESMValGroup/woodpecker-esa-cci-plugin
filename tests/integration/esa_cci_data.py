"""ESA CCI datasets from the ESA CCI Open Data Portal for the tests.

The datasets are available from three stores, named after the xcube-cci
data stores that open them:

- ``ccizarr``: zarr datasets, opened with s3fs.
- ``ccikc``: Kerchunk references to the original netCDF files, opened with
  fsspec.
- ``cciodp``: the original netCDF files, opened with the xcube-cci Open
  Data Portal store. It only works with xcube-cci, so tests of these
  datasets are skipped without it.
"""

from importlib.metadata import version
from typing import Literal, NamedTuple

import pytest
import woodpecker
import xarray as xr
from woodpecker.io.backends.xr import XarrayInput

Store = Literal["ccizarr", "ccikc", "cciodp"]

# The ESA CCI zarr store, as used by the xcube-cci "ccizarr" data store.
BUCKET = "esacci"
STORAGE_OPTIONS = {
    "anon": True,
    "client_kwargs": {"endpoint_url": "https://cci-ke-o.s3-ext.jc.rl.ac.uk"},
}
# The Kerchunk references of the xcube-cci "ccikc" data store.
KERCHUNK_URL = (
    "https://data.cci.ceda.ac.uk/thredds/fileServer/esacci/water_vapour/"
    "metadata/kerchunk/TCWV-land/L3/v3.2"
)
KERCHUNK_REFERENCES = {
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-20020701-20171231-fv3.2-kr1.1": (
        "0.05deg/daily"
    ),
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-05deg-20020701-20171231-fv3.2-kr1.1": (
        "0.5deg/daily"
    ),
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-200207-201712-fv3.2-kr1.1": (
        "0.05deg/monthly"
    ),
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-05deg-200207-201712-fv3.2-kr1.1": (
        "0.5deg/monthly"
    ),
}
# The number of time steps that the tests write to netCDF files.
SUBSET_TIME_STEPS = 2
# The dask chunks of the zarr and Kerchunk datasets: the time steps that the
# tests write are a single chunk, so only those are read. Spatially, the
# chunks are ~128 MB, because the storage chunks of the 0.05 degree datasets
# are a few MB, and with those, each recipe step adds hundreds of thousands
# of tasks to the dask graph, which takes GBs of memory.
CHUNKS = {"time": SUBSET_TIME_STEPS, "lat": "auto", "lon": "auto"}
# The daily Kerchunk datasets store the time bounds in a chunk per day, and
# the recipes read all of them, which takes long, so the tests only use the
# first time steps, unless pytest runs with --full-time-axis.
KERCHUNK_TIME_STEPS = 3
# The Open Data Portal store reads each time step from a separate netCDF
# file over OPeNDAP, so the tests only use the first time steps, unless
# pytest runs with --full-time-axis.
ODP_TIME_RANGES = {
    "day": ["2003-01-01", "2003-01-03"],
    "mon": ["2003-01-01", "2003-03-31"],
}
# The Open Data Portal datasets of the water vapour recipes.
ODP_WATER_VAPOUR = (
    "esacci.WATERVAPOUR.{frequency}.L3S.TCWV.multi-sensor.multi-platform."
    "TCWV_land_{resolution}.{version}.r1"
)


class Case(NamedTuple):
    """A dataset and the CMIP7 variable its recipe provides.

    The recipe stores the realm, branded variable and frequency of the CMIP7
    variable in the global attributes.
    """

    store: Store
    data_id: str
    variable_id: str

    @property
    def id(self) -> str:
        """Return a short name of the case for test ids."""
        return f"{self.variable_id}-{self.store}-{self.data_id}"


CASES = [
    Case(
        "ccizarr",
        "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr",
        "prw",
    ),
    Case(
        "ccizarr",
        "ESACCI-L4_GHRSST-SST-GMPE-GLOB_CDR2.0-1981-2016-v02.0-fv01.0.zarr",
        "tos",
    ),
    *(Case("ccikc", data_id, "prw") for data_id in KERCHUNK_REFERENCES),
    *(
        Case(
            "cciodp",
            f"esacci.SST.day.L4.{data_id}",
            "tos",
        )
        for data_id in (
            "SSTdepth.multi-sensor.multi-platform.OSTIA.1-1.r1",
            "SSTdepth.multi-sensor.multi-platform.OSTIA.2-1.sst",
            "SSTskin.Unspecified.Unspecified.GMPE.2-0.r1",
        )
    ),
    *(
        Case(
            "cciodp",
            ODP_WATER_VAPOUR.format(
                frequency=frequency, resolution=resolution, version=version
            ),
            "prw",
        )
        for frequency in ("day", "mon")
        for resolution in ("005deg", "05deg")
        for version in ("3-2", "4-2")
    ),
]


def _open_dataset(
    case: Case,
    *,
    decode_times: bool,
    full_time_axis: bool,
) -> xr.Dataset:
    """Open the dataset of ``case`` lazily.

    Without ``full_time_axis``, only the first time steps of the Kerchunk and
    Open Data Portal datasets are opened.
    """
    dataset: xr.Dataset
    if case.store == "ccizarr":
        dataset = xr.open_zarr(
            f"s3://{BUCKET}/{case.data_id}",
            chunks=CHUNKS,
            storage_options=STORAGE_OPTIONS,
            decode_times=decode_times,
        )
    elif case.store == "ccikc":
        url = f"{KERCHUNK_URL}/{KERCHUNK_REFERENCES[case.data_id]}"
        # zarr 3 only reads from asynchronous file systems, while zarr 2
        # only reads from synchronous ones.
        asynchronous = not version("zarr").startswith("2.")
        dataset = xr.open_zarr(
            "reference://",
            chunks=CHUNKS,
            consolidated=False,
            decode_times=decode_times,
            storage_options={
                "fo": f"{url}/{case.data_id}.json",
                "remote_protocol": "https",
                "asynchronous": asynchronous,
                "remote_options": {"asynchronous": asynchronous},
            },
        )
        if not full_time_axis:
            dataset = dataset.isel(time=slice(KERCHUNK_TIME_STEPS))
    else:
        xcube_store = pytest.importorskip("xcube.core.store")
        if not decode_times:
            pytest.skip("The Open Data Portal store always decodes the times")
        store = xcube_store.new_data_store("cciodp")
        if full_time_axis:
            # The store has no option to set the chunks.
            dataset = store.open_data(case.data_id).chunk(CHUNKS)
        else:
            # With only a few time steps, the dask graph is small with the
            # storage chunks, and larger dask chunks would read more files.
            frequency = case.data_id.split(".")[2]
            dataset = store.open_data(
                case.data_id,
                time_range=ODP_TIME_RANGES[frequency],
            )
    return dataset


def open_fixed_dataset(
    case: Case,
    *,
    decode_times: bool = True,
    full_time_axis: bool = False,
) -> xr.Dataset:
    """Open the dataset of ``case`` lazily and apply the recipe matching it.

    Woodpecker selects the recipe by matching the recipe ``path_patterns``
    against the data id, so the data id is passed as the input name. With
    ``decode_times=False``, the times are kept as numbers. Without
    ``full_time_axis``, only the first time steps of the Kerchunk and Open
    Data Portal datasets are used.
    """
    dataset = _open_dataset(
        case,
        decode_times=decode_times,
        full_time_axis=full_time_axis,
    )
    woodpecker.recipe.apply(
        XarrayInput(payload=dataset, name=case.data_id),
        woodpecker.recipe.catalog(),
        dry_run=False,
    )
    return dataset
