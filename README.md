# woodpecker-esa-cci-plugin

ESA CCI fixes and recipes for
[Woodpecker](https://github.com/roocs/woodpecker).

This plugin registers:

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
- Recipe `esa_cci.water_vapour`: sets the `standard_name`, `long_name`,
  `cell_methods` and `grid_mapping` of `tcwv`, makes `crs` a CF grid mapping,
  selects `tcwv`, renames it to `prw`, converts it to `kg m-2`, and makes
  latitude increasing. It combines the fixes above with the core woodpecker
  fixes `rename_variables`, `convert_units` and
  `ensure_latitude_is_increasing`.

## How it works

- The `woodpecker.plugins` entry point in `pyproject.toml` points at the
  `woodpecker_esa_cci_plugin` package. Woodpecker imports it at startup, and
  the `@register_fix_function` decorator registers each fix.
- Fix ids get their prefix from the package name:
  `woodpecker_esa_cci_plugin` becomes `esa_cci`.
- Recipes in `src/woodpecker_esa_cci_plugin/recipes/*.yaml` are discovered
  automatically.

## Loading data with xcube

The optional `xcube` extra installs [xcube](https://github.com/xcube-dev/xcube)
and its [ESA CCI plugin](https://github.com/esa-cci/xcube-cci) for loading
data from the ESA CCI Open Data Portal:

```bash
pip install "woodpecker-esa-cci-plugin[xcube]"
```

xcube depends on GDAL, which PyPI only ships as source code, so this needs
GDAL installed on your system (e.g. `libgdal-dev` on Debian/Ubuntu). The
`xcube` pixi environment below installs everything from conda-forge instead,
which avoids this.

## Development

Requires [pixi](https://pixi.sh). Dependencies come from conda-forge and are
pinned in `pixi.lock`.

```bash
pixi install                  # create the default environment in .pixi/
pixi run pre-commit install   # run ruff, mypy and basic checks on commit
pixi run test                 # run the tests
pixi run lint                 # run all pre-commit checks
```

Other environments, selected with `-e`:

- `py311`, `py314`: lowest and most recent supported Python version.
- `xcube`: includes xcube, xcube-cci, ncdata and iris, e.g.
  `pixi run -e xcube test`. This also runs the integration tests, which load
  data from the ESA CCI Open Data Portal and need internet access. Select them
  with `-m integration`.

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
