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

This plugin supports the following datasets from the ESA CCI Open Data Portal:

- Water vapour: `ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr`
- Sea surface temperature: `ESACCI-L4_GHRSST-SST-GMPE-GLOB_CDR2.0-1981-2016-v02.0-fv01.0.zarr`

## Recipes and fixes

A fix corrects one kind of problem, e.g. it converts variables to other
units or removes attributes that are not allowed by the CF conventions. Most
fixes have options that configure what they do, such as the variables and
the units to convert them to. Each fix can check a dataset and report the
problems it finds, or apply the correction.

A recipe contains the fixes for one dataset: a list of steps, each of
which is a fix with its options, that runs in order. Woodpecker selects the
recipe for a dataset by matching the path patterns of the recipe against
the name of the input, e.g. `*ESACCI-WATERVAPOUR-*`. This plugin provides
one recipe for each supported dataset.

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
