# woodpecker-esa-cci-plugin

[![codecov](https://codecov.io/gh/esmvalgroup/woodpecker-esa-cci-plugin/graph/badge.svg)](https://codecov.io/gh/esmvalgroup/woodpecker-esa-cci-plugin)

ESA CCI fixes and recipes for
[Woodpecker](https://github.com/roocs/woodpecker).

## Usage

Install this plugin together with woodpecker, and woodpecker finds its
fixes and recipes automatically. For example, to fix the ESA CCI water
vapour dataset from the
[ESA CCI Open Data Portal](https://climate.esa.int/en/data/), which needs
[s3fs](https://s3fs.readthedocs.io) to open the zarr store:

```python
import woodpecker
import xarray as xr
from woodpecker.io.backends.xr import XarrayInput

data_id = "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr"
dataset = xr.open_zarr(
    f"s3://esacci/{data_id}",
    chunks="auto",
    storage_options={
        "anon": True,
        "client_kwargs": {
            "endpoint_url": "https://cci-ke-o.s3-ext.jc.rl.ac.uk",
        },
    },
)

# Woodpecker selects the recipe by matching the recipe path patterns
# against the input name, and fixes the dataset in place.
woodpecker.recipe.apply(
    XarrayInput(payload=dataset, name=data_id),
    woodpecker.recipe.catalog(),
    dry_run=False,
)

# Write the first month.
dataset.isel(time=0).to_netcdf("prw.nc")
```

The data stays lazy, so only the part that is written is downloaded. Use
`woodpecker.recipe.check` instead of `woodpecker.recipe.apply` to list the
problems without fixing them.

## Supported datasets

This plugin supports the following datasets from the ESA CCI Open Data
Portal. They are available from three stores, which the
[xcube ESA CCI plugin](https://github.com/esa-cci/xcube-cci) opens as the
`ccizarr`, `ccikc` and `cciodp` data stores. The data id is the name to
pass to woodpecker.

- Water vapour, total column, as the CMIP7 variable `prw`:
  - zarr store: `ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr`
  - Kerchunk store, daily and monthly v3.2 at 0.05° and 0.5°:
    `ESACCI-WATERVAPOUR-L3C-TCWV-meris-*-fv3.2-kr1.1`
  - Open Data Portal store, daily and monthly v3.2 and v4.2 at 0.05° and
    0.5°:
    `esacci.WATERVAPOUR.{day,mon}.L3S.TCWV.multi-sensor.multi-platform.TCWV_land_*.{3-2,4-2}.r1`
- Sea surface temperature, daily level 4 analyses, as the CMIP7 variable
  `tos`:
  - zarr store, GMPE:
    `ESACCI-L4_GHRSST-SST-GMPE-GLOB_CDR2.0-1981-2016-v02.0-fv01.0.zarr`
  - Open Data Portal store, GMPE and OSTIA:
    `esacci.SST.day.L4.SSTskin.Unspecified.Unspecified.GMPE.2-0.r1`,
    `esacci.SST.day.L4.SSTdepth.multi-sensor.multi-platform.OSTIA.1-1.r1`
    and `esacci.SST.day.L4.SSTdepth.multi-sensor.multi-platform.OSTIA.2-1.sst`
- Sea surface salinity, monthly level 4 analyses, as the CMIP7 variable
  `sos`, from the 30-day means centred on the 15th of each month. The
  datasets also have the overlapping 30-day means centred on the 1st,
  which the recipe removes:
  - Kerchunk store, v2.31, v3.21, v4.41 and v5.5:
    `ESACCI-SEASURFACESALINITY-L4-SSS-{,GLOBAL-}MERGED_OI_Monthly_CENTRED_15Day_*`
  - Open Data Portal store, the same versions:
    `esacci.SEASURFACESALINITY.15-days.L4.SSS.multi-sensor.multi-platform.{,GLOBAL-}MERGED_OI_Monthly_CENTRED_15Day_*.r1`
- Cloud, monthly AVHRR v3.0, as the CMIP7 variables `clt`, `lwp`, `clivi`,
  the top of atmosphere fluxes `rlut`, `rlutcs`, `rsut`, `rsutcs` and
  `rsdt`, and the surface fluxes `rlus`, `rsus`, `rsuscs`, `rlds`,
  `rldscs`, `rsds` and `rsdscs`:
  - zarr store, `clt` only:
    `ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_NOAA-1982-2016-fv3.0.zarr`
  - Kerchunk store, the morning and afternoon orbits:
    `ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_{AM,PM}-*-fv3.0-kr1.1`
  - Open Data Portal store, the same:
    `esacci.CLOUD.mon.L3C.CLD_PRODUCTS.multi-sensor.multi-platform.AVHRR-{AM,PM}.3-0.r1`
- Aerosol, daily and monthly SU v4.3, as the CMIP7 variables `od550aer`,
  `od550lt1aer` and `abs550aer`:
  - Open Data Portal store, ATSR-2 and AATSR:
    `esacci.AEROSOL.{day,mon}.L3C.AER_PRODUCTS.{ATSR-2.ERS-2,AATSR.Envisat}.SU.4-3.r1`
- Snow, daily, as the CMIP7 variables `snc`, from the snow cover fraction
  on the ground, and `snw`, from the snow water equivalent:
  - zarr store, `snw` v1.0 and v2.0: `ESACCI-L3C_SNOW-SWE-*-fv*.zarr`
  - Kerchunk store, `snc` and `snw` v2.0:
    `ESACCI-L3C_SNOW-SCFG-AVHRR_MERGED-19820101-20181230-fv2.0_kr1.0` and
    `ESACCI-L3C_SNOW-SWE-MERGED-19790102-20200524-fv2.0_kr1.2`
  - Open Data Portal store, `snc` v2.0 and `snw` v2.0, v3.1 and v4.0:
    `esacci.SNOW.day.L3C.SCFG.multi-sensor.multi-platform.AVHRR_MERGED.2-0.r1`
    and `esacci.SNOW.day.L3C.SWE.multi-sensor.multi-platform.MERGED.*.r1`
- Sea ice concentration, daily SSM/I and SSMIS v3.0 at 12.5 km, as the
  CMIP7 variable `siconc`, for the northern and the southern hemisphere,
  on the polar EASE-Grid 2.0 (x/y) with 2-D latitudes and longitudes:
  - Open Data Portal store:
    `esacci.SEAICE.day.L4.SICONC.multi-sensor.multi-platform.RE_SSMI_12-5kmEASE2-{NH,SH}.3-0.{NH,SH}`

The cloud and aerosol datasets provide several variables, each from its own
recipe, named `esa_cci.<essential climate variable>_<variable>`, e.g.
`esa_cci.cloud_clt`, with a `_daily` suffix for the daily aerosol
datasets. Woodpecker raises an error when several recipes match, so pass
the recipe id:

```python
woodpecker.recipe.apply(
    XarrayInput(payload=dataset, name=data_id),
    woodpecker.recipe.catalog(),
    recipe_id="esa_cci.cloud_clt",
    dry_run=False,
)
```

Each recipe keeps only its own variable, so open the dataset again for each
variable. Datasets in which some calendar months or days have no data,
such as the AVHRR afternoon orbit cloud dataset, get those time steps, with
missing values, as CMIP7 requires a time coordinate without gaps.

The recipes keep the uncertainty information as ancillary variables, which
iris loads as ancillary variables of the cube:

- Water vapour: `tcwv_err`, the mean of the retrieval uncertainties, as the
  standard error of `prw`; `tcwv_ran`, their root mean square; `stdv`, the
  standard deviation of the retrievals; and in v3.2 `num_obs`, the number
  of retrievals.
- Sea surface temperature: the standard error of `tos`, `analysis_error`
  in OSTIA 1-1 and `analysed_sst_uncertainty` in OSTIA 2-1, and for GMPE
  the spread and the size of the ensemble of analyses, `standard_deviation`
  and `analysis_number`.
- Sea surface salinity: `sss_random_error`, the standard error of `sos`,
  and `total_nobs`, the number of observations.
- Cloud fraction: `cfc_unc`, the mean of the pixel uncertainties, as the
  standard error of `clt`; `cfc_prop_unc`, the uncertainty propagated
  from the pixels, except in the zarr store; `cfc_std`, the standard
  deviation over the month; and `nobs`, the number of observations. The
  other cloud variables have no uncertainty variables.
- Aerosol optical depth: `AOD550_uncertainty`, the propagated uncertainty
  including sampling, as the standard error of `od550aer`;
  `AOD550_uncertainty_mean`, the mean of the pixel uncertainties; the
  standard deviations `AOD550_sdev`, `FM_AOD550_sdev` and `AAOD550_sdev`
  of `od550aer`, `od550lt1aer` and `abs550aer`; and `pixel_count`, the
  number of observations.
- Snow: `scfg_unc` and `swe_std`, the standard errors of `snc` and `snw`.
- Sea ice concentration: `total_standard_uncertainty`, the standard error
  of `siconc`. The `status_flag` is not kept.

The 0.05° daily datasets have storage chunks of a few MB, so with those as
dask chunks, each recipe step adds hundreds of thousands of tasks to the
dask graph, which takes several GB of memory. Use dask chunks of ~128 MB
instead: pass `chunks="auto"` to `xr.open_zarr`, or rechunk datasets
from the xcube-cci Kerchunk and Open Data Portal stores, which have no
option for the chunks, before applying the recipe:

```python
from xcube.core.store import new_data_store

data_id = (
    "esacci.WATERVAPOUR.day.L3S.TCWV.multi-sensor.multi-platform."
    "TCWV_land_005deg.3-2.r1"
)
dataset = new_data_store("cciodp").open_data(data_id).chunk("auto")
```

For the CMIP7 variables that other ESA CCI datasets could provide, see
[docs/cmip7_variable_mapping.md](docs/cmip7_variable_mapping.md).

## Recipes and fixes

A fix corrects one kind of problem, e.g. it converts variables to other
units or removes attributes that are not allowed by the CF conventions. Most
fixes have options that configure what they do, such as the variables and
the units to convert them to. Each fix can check a dataset and report the
problems it finds, or apply the correction.

A recipe contains the fixes for one dataset: a list of steps, each of
which is a fix with its options, that runs in order. Woodpecker selects the
recipe for a dataset by matching the path patterns of the recipe against
the name of the input, e.g. `*ESACCI-L4_GHRSST-SST-GMPE-GLOB_*`. This plugin
provides one recipe for each group of datasets that need the same fixes,
e.g. the monthly water vapour datasets of version 3.2 in all stores.

To list the recipes, run:

```bash
pixi run woodpecker list-recipes
```

This also lists the recipes that come with woodpecker itself. Add
`--format json` to show the full recipes, including their path patterns and
the options of each step.

To list the fixes this plugin provides, with a description of each, run:

```bash
pixi run woodpecker list-fixes --dataset ESA-CCI
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a development
environment and run the tests.

## License

Apache-2.0, see [LICENSE](LICENSE).
