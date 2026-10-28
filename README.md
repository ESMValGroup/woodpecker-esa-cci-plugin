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

The recipes keep the uncertainty information as ancillary variables of
`prw` and `tos`, which iris loads as ancillary variables of the cube:

- Water vapour: `tcwv_err`, the mean of the retrieval uncertainties, as the
  standard error of `prw`; `tcwv_ran`, their root mean square; `stdv`, the
  standard deviation of the retrievals; and in v3.2 `num_obs`, the number
  of retrievals.
- Sea surface temperature: the standard error of `tos`, `analysis_error`
  in OSTIA 1-1 and `analysed_sst_uncertainty` in OSTIA 2-1, and for GMPE
  the spread and the size of the ensemble of analyses, `standard_deviation`
  and `analysis_number`.

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
