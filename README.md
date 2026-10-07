# woodpecker-esa-cci-plugin

[![codecov](https://codecov.io/gh/esmvalgroup/woodpecker-esa-cci-plugin/graph/badge.svg)](https://codecov.io/gh/esmvalgroup/woodpecker-esa-cci-plugin)

ESA CCI fixes and recipes for
[Woodpecker](https://github.com/roocs/woodpecker).

This plugin registers:

- Fix `esa_cci.remove_packing`: removes the packing encoding (`dtype`,
  `scale_factor`, `add_offset`, `_FillValue`, `missing_value` and
  `_Unsigned`) from all variables, except variables with decoded times, whose
  encoding defines the units and calendar they are written in. xarray keeps
  the packing encoding when values change through `copy(data=...)` or in
  place, and then writes values that no longer fit. The recipe output is
  therefore not packed, unless the encoding is set again when writing.
- Fix `esa_cci.remove_range_attributes`: removes the range attributes
  `actual_range`, `valid_min`, `valid_max` and `valid_range` from all
  variables. xarray does not use them, and they become invalid as soon as
  the values change.
- Fix `esa_cci.set_attributes`: sets attributes on variables where they are
  missing or wrong. The correct values are configured with the `attributes`
  option, a mapping from variable name to a mapping of attribute names to
  values. Attributes set to `null` are removed.
- Fix `esa_cci.select_variables`: drops all data variables except the ones
  configured with the `variables` option and the variables they refer to
  through CF attributes, such as ancillary variables and coordinate bounds.
- Fix `esa_cci.grid_mapping_from_wkt`: sets the CF grid mapping attributes
  of the variable configured with the `variable` option from the WKT string
  in its `wkt_attribute` attribute, using
  [pyproj](https://pyproj4.github.io/pyproj/). The WKT attribute is replaced
  by the CF `crs_wkt` attribute.
- Fix `esa_cci.convert_units`: converts the variables configured with the
  `units` option, a mapping from variable name to units, using
  [pint](https://pint.readthedocs.io) with the
  [cf-xarray](https://cf-xarray.readthedocs.io) units registry. Unlike the
  core woodpecker `convert_units` fix, it sets the units attribute to the
  configured string, so the result can follow the CF conventions. The range
  attributes and packing encoding of the converted variables are removed.
- Fix `esa_cci.normalize_longitude`: wraps the longitude dimension coordinate
  configured with the `coordinate` option, and its bounds, to [0, 360) and
  reorders the data so the coordinate stays increasing. Their range attributes,
  such as `valid_range`, are removed. Unlike the core
  woodpecker `normalize_longitude_convention` fix, the result is monotonic.
- Recipe `esa_cci.water_vapour`: removes the packing encoding and range
  attributes; sets the `standard_name`, `long_name`, `cell_methods` and
  `grid_mapping` of `tcwv` and converts it to `kg m-2`; removes invalid
  standard names and the attributes that bounds variables inherit from their
  coordinates; replaces hyphens in global attribute names and sets
  `Conventions` to `CF-1.11`; stores time in the `standard` calendar and
  marks it as not counting leap seconds; makes `crs` a CF grid mapping;
  selects `tcwv`; makes latitude increasing; wraps longitude to [0, 360); and
  renames `tcwv` to `prw`. It combines the fixes above with the core
  woodpecker fixes `rename_variables` and `ensure_latitude_is_increasing`.
  The result passes the ESMValCore CMIP7 CMOR check as `atmos` variable
  `prw` and all CF 1.11 checks of the IOOS compliance checker.
- Fix `esa_cci.set_time_units`: sets the units and calendar that the decoded
  time coordinate configured with the `coordinate` option, and its bounds,
  are stored in to the `units` option, e.g. `days since 1850-01-01`, and the
  `calendar` option, e.g. `standard`. The time values do not change, only
  how they are written.
- Fix `esa_cci.set_global_attributes`: renames the global attributes
  configured with the `rename` option, a mapping from current to new name,
  and then sets the ones configured with the `attributes` option, a mapping
  from attribute name to value, where they are missing or wrong. Attributes
  set to `null` are removed.
- Recipe `esa_cci.sea_surface_temperature`: removes the packing encoding
  and range attributes; sets the `standard_name`, `long_name`,
  `cell_methods` and `units_metadata` of `analysed_sst` and converts it to
  `degC`; sets `Conventions` to `CF-1.11` and removes the empty global
  `comment`; stores time in days since 1850-01-01 in the `standard` calendar
  and marks it as not counting leap seconds; selects `analysed_sst`; wraps
  longitude to [0, 360); and renames `analysed_sst` to `tos`. The result
  passes the ESMValCore CMIP7 CMOR check as `ocean` variable `tos` and all
  CF 1.11 checks of the IOOS compliance checker.

The fixes are strict: they raise an error when a configured variable or
attribute does not exist or an option is empty, instead of silently doing
nothing. A fix without any options does nothing.

## How it works

- The `woodpecker.plugins` entry point in `pyproject.toml` points at the
  `woodpecker_esa_cci_plugin` package. Woodpecker imports it at startup, and
  the `@register_fix_function` decorator registers each fix.
- Each fix is a module in `src/woodpecker_esa_cci_plugin/fixes/`, and its
  tests are in `tests/unit/fixes/`.
- Fix ids get their prefix from the package name:
  `woodpecker_esa_cci_plugin` becomes `esa_cci`.
- Recipes in `src/woodpecker_esa_cci_plugin/recipes/*.yaml` are discovered
  automatically.

## Development

Requires [pixi](https://pixi.sh). Dependencies come from conda-forge and are
pinned in `pixi.lock`.

```bash
pixi install                  # create the default environment in .pixi/
pixi run pre-commit install   # run ruff, mypy and basic checks on commit
pixi run test                 # run the tests and report coverage
pixi run lint                 # run all pre-commit checks
```

Other environments, selected with `-e`:

- `py311`, `py314`: lowest and most recent supported Python version.
- `xcube`: includes [xcube](https://github.com/xcube-dev/xcube), its
  [ESA CCI plugin](https://github.com/esa-cci/xcube-cci), ncdata and iris, e.g.
  `pixi run -e xcube test`. This also runs the integration tests in
  `tests/integration`, which load data from the ESA CCI Open Data Portal and
  need internet access. Run only those with
  `pixi run -e xcube test tests/integration`, or only the unit tests with
  `pixi run test tests/unit`.
- `online`: includes [ESMValCore](https://github.com/ESMValGroup/ESMValCore),
  ncdata, s3fs and the
  [IOOS compliance checker](https://github.com/ioos/compliance-checker), and
  runs the integration tests that check the recipe output against the CMIP7
  CMOR tables and the CF conventions, and that it loads with iris. These tests
  need internet access. ESMValCore needs zarr 3 and xcube-cci
  needs zarr 2, so these tests open the ESA CCI zarr store directly with s3fs.

Check that woodpecker picks up the plugin:

```bash
pixi run woodpecker list-fixes --dataset ESA-CCI
pixi run woodpecker list-recipes
```

Versions come from git tags via setuptools-scm, using the `calver-by-date`
scheme (e.g. `26.9.28`).

## Using this repository as a template

1. Rename the package directory `src/woodpecker_esa_cci_plugin` to
   `src/woodpecker_<name>_plugin`. The fix id prefix becomes `<name>`.
2. Update the project name, entry point and package-data key in
   `pyproject.toml`.
3. Replace the example fix and recipe, and update the tests.

## License

Apache-2.0, see [LICENSE](LICENSE).
