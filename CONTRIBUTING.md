# Contributing

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
- `online`: includes the
  [IOOS compliance checker](https://github.com/ioos/compliance-checker),
  [iris](https://scitools.org.uk/iris/docs/latest/), and
  [ESMValCore](https://github.com/ESMValGroup/ESMValCore), and
  runs the integration tests that check the recipe output against the CF
  conventions and the CMIP7 CMOR tables, and that it loads without warnings
  with iris. These tests need internet access.
  ESMValCore needs zarr 3 and xcube-cci needs zarr 2, so these tests open the
  ESA CCI zarr store directly with s3fs.
  It also includes the CMIP7 checker of
  [cc-plugin-wcrp](https://github.com/ESGF/cc-plugin-wcrp), which checks the
  recipe output against the CMIP7 vocabularies, except for the global
  attributes and how the data is stored. Download the vocabularies once,
  into `.pixi/esgvoc`, with
  `pixi run -e online esgvoc use cmip7@latest universe@latest`.
- `xcube`: includes [xcube](https://github.com/xcube-dev/xcube), its
  [ESA CCI plugin](https://github.com/esa-cci/xcube-cci), ncdata and iris, e.g.
  `pixi run -e xcube test`. This also runs the integration tests in
  `tests/integration`, which load data from the ESA CCI Open Data Portal and
  need internet access. Run only those with
  `pixi run -e xcube test tests/integration`, or only the unit tests with
  `pixi run test tests/unit`.

Check that woodpecker picks up the plugin:

```bash
pixi run woodpecker list-fixes --dataset ESA-CCI
pixi run woodpecker list-recipes
```

Versions come from git tags via setuptools-scm, using the `calver-by-date`
scheme (e.g. `2026.9.28`).
