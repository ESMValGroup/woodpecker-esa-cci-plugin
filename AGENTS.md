# Agent instructions

This is a [Woodpecker](https://github.com/roocs/woodpecker) plugin with fixes
and recipes that make ESA CCI datasets follow the CF conventions and the
CMIP7 data request. Woodpecker finds it through the `woodpecker.plugins`
entry point in `pyproject.toml`. The README is written for users, and
CONTRIBUTING.md for developers.

## Development environment

The project uses [pixi](https://pixi.sh). The environments are defined in
`pyproject.toml`:

- `default`: the package and the development tools.
- `online`: adds ESMValCore, s3fs and the IOOS compliance checker for the
  integration tests that open the data from the ESA CCI Open Data Portal.
- `xcube`: adds xcube and xcube-cci for the integration tests that use the
  xcube ESA CCI data store.
- `py311` and `py314`: the lowest and most recent supported Python versions.

`online` and `xcube` cannot be combined, because ESMValCore and xcube-cci
require incompatible versions of zarr.

Commands:

```bash
pixi run test   # pytest, with coverage
pixi run lint   # pre-commit: ruff, mypy and basic checks
```

Run both before considering a change done. Ruff enables all rules with a
line length of 79, and mypy runs in strict mode on `src` and `tests`. After
changing the dependencies in `pyproject.toml`, run `pixi lock`.

## Code layout

- `src/woodpecker_esa_cci_plugin/fixes/`: one fix per module. A fix is a
  subclass of `ConfigurableFix` from `configurable_fix.py`, registered with
  `@register_fix_function`. Its recipe options are a pydantic model, so
  unknown or invalid options raise an error. Fixes without options use
  `Options` itself. The `description` of a fix is its user documentation,
  shown by `woodpecker list-fixes`, so it describes the options and why the
  fix is needed.
- `src/woodpecker_esa_cci_plugin/__init__.py`: imports all fixes, which
  registers them. Add new fixes here.
- `src/woodpecker_esa_cci_plugin/recipes/`: one YAML file per dataset.
  Woodpecker selects a recipe by matching its `path_patterns` against the
  input name. Steps run in the order listed, each fix at most once per
  recipe, and variables are renamed last so that all other steps use the
  original names.

## Tests

- `tests/unit/`: fast tests on a small synthetic dataset from
  `synthetic_esa_cci_data.py` that mimics the real data, including its
  encoding.
- `tests/integration/`: tests on the real datasets listed in
  `esa_cci_data.py`. They check that the recipes match the datasets, and
  that the output passes the CF compliance checker and the ESMValCore CMIP7
  CMOR check, loads with iris, and that the synthetic dataset still looks
  like the real one.

The integration tests are skipped in the `default` environment, because
their dependencies are not installed there. Make sure the `online` and
`xcube` environments are installed, and after a change that affects a fix or
recipe that the integration tests use, run them in both. They take less than
a minute:

```bash
pixi run -e online pytest tests/integration
pixi run -e xcube pytest tests/integration
```

Each environment skips the tests that need the other one. Check that the
tests you expect to run pass and are not skipped.
