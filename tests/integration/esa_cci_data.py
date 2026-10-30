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
from typing import Any, Literal, NamedTuple

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
# The Kerchunk references of the xcube-cci "ccikc" data store: the
# directory below KERCHUNK_URL of the references of each dataset, as listed
# in xcube_cci/data/kc_refs.json.
KERCHUNK_URL = "https://data.cci.ceda.ac.uk/thredds/fileServer/esacci"
WATER_VAPOUR_REFERENCES = "water_vapour/metadata/kerchunk/TCWV-land/L3/v3.2"
SALINITY_REFERENCES = "sea_surface_salinity/metadata/kerchunk"
KERCHUNK_REFERENCES = {
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-20020701-20171231-fv3.2-kr1.1": (
        f"{WATER_VAPOUR_REFERENCES}/0.05deg/daily"
    ),
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-05deg-20020701-20171231-fv3.2-kr1.1": (
        f"{WATER_VAPOUR_REFERENCES}/0.5deg/daily"
    ),
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-200207-201712-fv3.2-kr1.1": (
        f"{WATER_VAPOUR_REFERENCES}/0.05deg/monthly"
    ),
    "ESACCI-WATERVAPOUR-L3C-TCWV-meris-05deg-200207-201712-fv3.2-kr1.1": (
        f"{WATER_VAPOUR_REFERENCES}/0.5deg/monthly"
    ),
    "ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_AM-199109-201612-fv3.0-kr1.1": (
        "cloud/metadata/kerchunk/version3/L3C/AVHRR-AM/v3.0"
    ),
    "ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_PM-198201-201612-fv3.0-kr1.1": (
        "cloud/metadata/kerchunk/version3/L3C/AVHRR-PM/v3.0"
    ),
    "ESACCI-L3C_SNOW-SCFG-AVHRR_MERGED-19820101-20181230-fv2.0_kr1.0": (
        "snow/metadata/kerchunk/scfg/AVHRR_MERGED/v2.0"
    ),
    "ESACCI-L3C_SNOW-SWE-MERGED-19790102-20200524-fv2.0_kr1.2": (
        "snow/metadata/kerchunk/swe/MERGED/v2.0"
    ),
    **{
        f"ESACCI-SEASURFACESALINITY-L4-SSS-{name}": (
            f"{SALINITY_REFERENCES}/{directory}/30days"
        )
        for name, directory in (
            (
                (
                    "MERGED_OI_Monthly_CENTRED_15Day_25km-20100101-20191215-"
                    "fv2.31_kr1.0"
                ),
                "v02.31",
            ),
            (
                (
                    "MERGED_OI_Monthly_CENTRED_15Day_25km-20100115-20200915-"
                    "fv3.21_kr1.0"
                ),
                "v03.21",
            ),
            (
                (
                    "GLOBAL-MERGED_OI_Monthly_CENTRED_15Day_0.25deg-20100115-"
                    "20221015-fv4.41_kr1.0"
                ),
                "v04.41/GLOBALv4.41",
            ),
            (
                (
                    "GLOBAL-MERGED_OI_Monthly_CENTRED_15Day_0.25deg-20100115-"
                    "20231215-fv5.5-kr1.0"
                ),
                "v05.5/GLOBALv5.5",
            ),
        )
    },
    (
        "ESACCI-OC-L3S-CHLOR_A-MERGED-1M_MONTHLY_4km_GEO_PML_OCx-199709-"
        "202212-fv6.0-kr1.1"
    ): (
        "ocean_colour/metadata/kerchunk/v6.0-release/geographic/netcdf/"
        "chlor_a/monthly/v6.0"
    ),
}
# The number of time steps that the tests use of the Kerchunk and Open Data
# Portal datasets, unless pytest runs with --full-time-axis, and that they
# write to netCDF files. The daily Kerchunk datasets store the time bounds
# in a chunk per day, and the recipes read all of them, which takes long,
# and the Open Data Portal store reads each time step from a separate
# netCDF file over OPeNDAP.
TIME_STEPS = 2
# The dask chunks of the zarr and Kerchunk datasets: the time steps that the
# tests write are a single chunk, so only those are read. Spatially, the
# chunks are ~128 MB, because the storage chunks of the 0.05 degree datasets
# are a few MB, and with those, each recipe step adds hundreds of thousands
# of tasks to the dask graph, which takes GBs of memory.
CHUNKS: dict[str, int | Literal["auto"]] = {
    "time": TIME_STEPS,
    "lat": "auto",
    "lon": "auto",
}
# The CMIP7 variables of the cloud recipes, each from its own recipe
# esa_cci.cloud_<variable>.
CLOUD_VARIABLES = (
    "clt",
    "lwp",
    "clivi",
    "rlut",
    "rlutcs",
    "rsut",
    "rsutcs",
    "rsdt",
    "rlus",
    "rsus",
    "rsuscs",
    "rlds",
    "rldscs",
    "rsds",
    "rsdscs",
)
# The cloud datasets that provide all of them.
CLOUD_DATASETS: tuple[tuple[Store, str], ...] = (
    *(
        ("ccikc", data_id)
        for data_id in KERCHUNK_REFERENCES
        if "CLOUD" in data_id
    ),
    *(
        (
            "cciodp",
            (
                "esacci.CLOUD.mon.L3C.CLD_PRODUCTS.multi-sensor."
                f"multi-platform.AVHRR-{orbit}.3-0.r1"
            ),
        )
        for orbit in ("AM", "PM")
    ),
)
# The Open Data Portal datasets of the water vapour recipes.
ODP_WATER_VAPOUR = (
    "esacci.WATERVAPOUR.{frequency}.L3S.TCWV.multi-sensor.multi-platform."
    "TCWV_land_{resolution}.{version}.r1"
)


class Case(NamedTuple):
    """A dataset and the CMIP7 variable its recipe provides.

    The recipe stores the realm, branded variable and frequency of the CMIP7
    variable in the global attributes. For datasets that provide several
    variables, each from its own recipe, ``recipe_id`` selects the recipe.
    Without --full-time-axis, ``opened_time_steps`` of the Kerchunk and Open
    Data Portal datasets are opened, which is more than ``TIME_STEPS`` for
    recipes that remove time steps.
    """

    store: Store
    data_id: str
    variable_id: str
    recipe_id: str | None = None
    opened_time_steps: int = TIME_STEPS

    @property
    def id(self) -> str:
        """Return the test id: the data id, and the recipe id if any."""
        if self.recipe_id is None:
            return self.data_id
        return f"{self.data_id}-{self.recipe_id}"


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
    *(
        Case("ccikc", data_id, "prw")
        for data_id in KERCHUNK_REFERENCES
        if "WATERVAPOUR" in data_id
    ),
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
    Case(
        "ccizarr",
        "ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_NOAA-1982-2016-fv3.0.zarr",
        "clt",
    ),
    *(
        Case(store, data_id, variable_id, f"esa_cci.cloud_{variable_id}")
        for store, data_id in CLOUD_DATASETS
        for variable_id in CLOUD_VARIABLES
    ),
    *(
        Case(
            "cciodp",
            f"esacci.AEROSOL.{frequency}.L3C.AER_PRODUCTS.{sensor}.SU.4-3.r1",
            variable_id,
            f"esa_cci.aerosol_{variable_id}{suffix}",
        )
        for frequency, suffix in (("mon", ""), ("day", "_daily"))
        for sensor in ("ATSR-2.ERS-2", "AATSR.Envisat")
        for variable_id in ("od550aer", "od550lt1aer", "abs550aer")
    ),
    Case(
        "ccikc",
        "ESACCI-L3C_SNOW-SCFG-AVHRR_MERGED-19820101-20181230-fv2.0_kr1.0",
        "snc",
    ),
    Case(
        "cciodp",
        "esacci.SNOW.day.L3C.SCFG.multi-sensor.multi-platform.AVHRR_MERGED."
        "2-0.r1",
        "snc",
    ),
    *(
        Case("ccizarr", f"ESACCI-L3C_SNOW-SWE-{years}.zarr", "snw")
        for years in ("1979-2018-fv1.0", "1979-2020-fv2.0")
    ),
    Case(
        "ccikc",
        "ESACCI-L3C_SNOW-SWE-MERGED-19790102-20200524-fv2.0_kr1.2",
        "snw",
    ),
    *(
        Case(
            "cciodp",
            "esacci.SNOW.day.L3C.SWE.multi-sensor.multi-platform.MERGED."
            f"{version}.r1",
            "snw",
        )
        for version in ("2-0", "3-1", "4-0")
    ),
    *(
        # Two time steps per month, of which the recipe keeps one.
        Case("ccikc", data_id, "sos", opened_time_steps=2 * TIME_STEPS)
        for data_id in KERCHUNK_REFERENCES
        if "SEASURFACESALINITY" in data_id
    ),
    *(
        Case(
            "cciodp",
            "esacci.SEASURFACESALINITY.15-days.L4.SSS.multi-sensor."
            f"multi-platform.{product}.r1",
            "sos",
            opened_time_steps=2 * TIME_STEPS,
        )
        for product in (
            "MERGED_OI_Monthly_CENTRED_15Day_25km.2-31",
            "MERGED_OI_Monthly_CENTRED_15Day_25km.3-21",
            "GLOBAL-MERGED_OI_Monthly_CENTRED_15Day_0-25deg.4-41",
            "GLOBAL-MERGED_OI_Monthly_CENTRED_15Day_0-25deg.5-5",
        )
    ),
    *(
        Case(
            "cciodp",
            "esacci.SEAICE.day.L4.SICONC.multi-sensor.multi-platform."
            f"RE_SSMI_12-5kmEASE2-{hemisphere}.3-0.{hemisphere}",
            "siconc",
        )
        for hemisphere in ("NH", "SH")
    ),
    Case(
        "cciodp",
        "esacci.OZONE.day.L3S.TC.multi-sensor.multi-platform.MERGED.fv0100.r1",
        "toz",
    ),
    Case(
        "cciodp",
        "esacci.OZONE.mon.L3.NP.multi-sensor.multi-platform.MERGED.fv0002.r1",
        "toz",
    ),
    *(
        Case("cciodp", f"esacci.OZONE.mon.L3.LP.{product}.v0001.r1", "o3")
        for product in (
            "GOMOS.Envisat.GOMOS_ENVISAT",
            "MIPAS.Envisat.MIPAS_ENVISAT",
            "OSIRIS.ODIN.OSIRIS_ODIN",
            "SCIAMACHY.Envisat.SCIAMACHY_ENVISAT",
            "SMR.ODIN.MZM",
            "SMR.ODIN.SMR_ODIN",
        )
    ),
    Case(
        "ccizarr",
        "ESACCI-OC-L3S-OC_PRODUCTS-MERGED-1M_MONTHLY_4km_GEO_PML_OCx_QAA-"
        "1997-2022-fv6.0.zarr",
        "chl",
    ),
    Case(
        "ccizarr",
        "ESACCI-OC-L3S-OC_PRODUCTS-MERGED-1D_DAILY_4km_GEO_PML_OCx_QAA-"
        "1997-2022-fv6.0.zarr",
        "chl",
    ),
    Case(
        "ccikc",
        "ESACCI-OC-L3S-CHLOR_A-MERGED-1M_MONTHLY_4km_GEO_PML_OCx-199709-"
        "202212-fv6.0-kr1.1",
        "chl",
    ),
    *(
        Case(
            "cciodp",
            f"esacci.OC.{frequency}.L3S.{product}.multi-sensor."
            "multi-platform.MERGED.6-0.geographic",
            "chl",
        )
        for frequency, product in (
            ("mon", "CHLOR_A"),
            ("mon", "OC_PRODUCTS"),
            ("day", "CHLOR_A"),
            ("day", "OC_PRODUCTS"),
        )
    ),
]
# The recipe steps that select the variables. The recipes run them first, so
# opening only the selected variables gives the same result.
SELECTION_FIXES = (
    "esa_cci.fix_variable_references",
    "esa_cci.select_variables",
)


def apply_recipe(
    case: Case,
    dataset: xr.Dataset,
    fixes: tuple[str, ...] | None = None,
) -> None:
    """Apply the recipe matching ``case`` to ``dataset``, in place.

    Woodpecker selects the recipe by matching the recipe ``path_patterns``
    against the data id, so the data id is passed as the input name, or by
    the recipe id of datasets with several recipes. With ``fixes``, only
    those steps of the recipe are applied.
    """
    woodpecker.recipe.apply(
        XarrayInput(payload=dataset, name=case.data_id),
        woodpecker.recipe.catalog(),
        recipe_id=case.recipe_id,
        fixes=fixes,
        dry_run=False,
    )


def select_variables(case: Case, dataset: xr.Dataset) -> None:
    """Keep the variables that the recipe of ``case`` keeps, in place."""
    apply_recipe(case, dataset, fixes=SELECTION_FIXES)


def _odp_variable_names(case: Case, store: Any) -> list[str]:  # noqa: ANN401
    """Return the variables of an Open Data Portal dataset to open.

    The store creates the dask arrays of all variables over the whole time
    axis when it opens a dataset, which takes GBs of memory for datasets
    with many variables, so only the variables that the recipe keeps are
    opened. They are selected from a dataset without data, made from the
    description of the dataset. The store adds the coordinates and the grid
    mapping of the variables.
    """
    description = store.describe_data(case.data_id)
    dataset = xr.Dataset(
        {
            name: xr.Variable((), 0, attrs=dict(variable.attrs or {}))
            for name, variable in description.data_vars.items()
        }
    )
    select_variables(case, dataset)
    return [str(name) for name in dataset.data_vars]


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
    else:
        xcube_store = pytest.importorskip("xcube.core.store")
        if not decode_times:
            pytest.skip("The Open Data Portal store always decodes the times")
        store = xcube_store.new_data_store("cciodp")
        dataset = store.open_data(
            case.data_id,
            variable_names=_odp_variable_names(case, store),
        )
        # The store has no option to set the chunks. With only a few time
        # steps, the dask graph is small with the storage chunks, and larger
        # dask chunks would read more files.
        # Polar grids have x/y dimensions instead of lat/lon, with storage
        # chunks of a whole time step.
        if full_time_axis:
            dataset = dataset.chunk(
                {
                    dim: size
                    for dim, size in CHUNKS.items()
                    if dim in dataset.dims
                }
            )
    if case.store != "ccizarr" and not full_time_axis:
        dataset = dataset.isel(time=slice(case.opened_time_steps))
    return dataset


def open_fixed_dataset(
    case: Case,
    *,
    decode_times: bool = True,
    full_time_axis: bool = False,
) -> xr.Dataset:
    """Open the dataset of ``case`` lazily and apply the recipe matching it.

    With ``decode_times=False``, the times are kept as numbers. Without
    ``full_time_axis``, only the first time steps of the Kerchunk and Open
    Data Portal datasets are used.
    """
    dataset = _open_dataset(
        case,
        decode_times=decode_times,
        full_time_axis=full_time_axis,
    )
    apply_recipe(case, dataset)
    return dataset
