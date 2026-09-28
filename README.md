# woodpecker-esa-cci-plugin

ESA CCI fixes and recipes for
[Woodpecker](https://github.com/roocs/woodpecker).

This plugin registers:

- Fix `esa_cci.add_tcwv_standard_name`: sets the CF `standard_name` on the
  `tcwv` variable when it is missing.
- Recipe `esa_cci.water_vapour`: combines the fix above with the core
  `woodpecker.ensure_latitude_is_increasing` fix.

## How it works

- The `woodpecker.plugins` entry point in `pyproject.toml` points at the
  `woodpecker_esa_cci_plugin` package. Woodpecker imports it at startup, and
  the `@register_fix_function` decorator registers each fix.
- Fix ids get their prefix from the package name:
  `woodpecker_esa_cci_plugin` becomes `esa_cci`.
- Recipes in `src/woodpecker_esa_cci_plugin/recipes/*.yaml` are discovered
  automatically.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                       # create .venv with runtime and dev dependencies
uv run pre-commit install     # run ruff, mypy and basic checks on commit
uv run pytest                 # run the tests
uv run pre-commit run --all-files
```

Check that woodpecker picks up the plugin:

```bash
uv run woodpecker list-fixes --dataset ESA-CCI
uv run woodpecker list-recipes
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
