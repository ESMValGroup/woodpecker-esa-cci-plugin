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

Run both before considering a change done. pre-commit only checks the files
that git tracks, so `git add` new files before running the lint. Ruff
enables all rules with a line length of 79, and mypy runs in strict mode on
`src` and `tests`. After changing the dependencies in `pyproject.toml`, run
`pixi lock`.

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
- `src/woodpecker_esa_cci_plugin/recipes/`: one YAML file per ECV, with
  one recipe per CMIP7 variable, named `esa_cci.<ecv>[_<variable>]`, that
  covers all versions of the datasets in the stores. Variables without a
  direct CMIP7 equivalent in `docs/cmip7_variable_mapping.md` get no
  recipe. Woodpecker selects a recipe by matching its `path_patterns`
  against the input name. Steps run in the order listed, each fix at most once per
  recipe, and variables are renamed last so that all other steps use the
  original names. The recipes select the variables first, with
  `esa_cci.fix_variable_references` and `esa_cci.select_variables`, so the
  other steps only process the variables that are kept, and the integration
  tests can open only those.

## Uncertainty variables

When adding a dataset, try to keep the variables that describe the
uncertainty of the selected variable, such as standard errors, retrieval
uncertainties, standard deviations and the number of observations, instead
of letting `esa_cci.select_variables` drop them. List them in the
`ancillary_variables` reference of the selected variable in
`esa_cci.fix_variable_references`: then they are kept, and iris loads them
as ancillary variables of the same cube. Check the product user guide for
what each one means, and give it a CF standard name where one fits, e.g.
`<standard_name> standard_error` for a standard error of `<standard_name>`,
or `number_of_observations` for a count. Uncertainties that are not a
standard error, such as a probability of misclassification, get no standard
name, only a `long_name` and a `comment` that say what they are.

Give the uncertainties the units of the selected variable, except counts,
which have units `1`. CF requires a standard error to have the units of
its variable and has no way to describe a relative uncertainty, so convert
uncertainties that are relative to the value, e.g. in percent of it, to
absolute ones with `esa_cci.convert_relative_uncertainties`. The units do
not tell the two apart when the variable is itself a fraction or a
percentage, so check the product user guide whether such an uncertainty is
in percentage points or relative to the value. Uncertainties that cannot be
made absolute, such as those of the logarithm of the variable, keep their
own dimensionless units and get no standard name.

Uncertainties of a temperature are temperature differences, so they need
`units_metadata: "temperature: difference"`, and `esa_cci.convert_units`
cannot convert them: it would subtract 273.15 when converting K to degC.
Since a difference has the same value in K and degC, set their units to
degC with `esa_cci.set_attributes` instead.

## Links to the documentation

When a recipe step, attribute or fix relies on the documentation of a
dataset, such as its product user guide, or on the CF conventions, link
the passage in the comment that explains it. Make the link as specific as
possible, so that a reader lands on the passage itself: for a PDF, give the
document version, the section and the page, and link the page with
`#page=<n>` (check that the page of the PDF file matches the printed page
number), and for a web page, link the anchor of the section. For example:

```yaml
# Section 2, "Cloud mask & fraction", on page 12 of the Product User Guide
# (D3.3, v5.1), defines the uncertainty of a pixel as ...:
# https://climate.esa.int/media/documents/Cloud_Product-User-Guide-PUG_v5.1.pdf#page=12
```

Do the same in the README and in `docs/cmip7_variable_mapping.md`, with
markdown links. Then reviewers and later changes can check the source
instead of trusting the comment.

## Tests

- `tests/unit/`: fast tests on a small synthetic dataset from
  `synthetic_esa_cci_data.py` that mimics the real data, including its
  encoding.
- `tests/integration/`: tests on the real datasets listed in
  `esa_cci_data.py`, from the zarr, Kerchunk and Open Data Portal stores.
  They check that the recipes match exactly these datasets, and
  that the output passes the CF compliance checker and the ESMValCore CMIP7
  CMOR check, loads with iris, and that the synthetic dataset still looks
  like the real one.

The integration tests are skipped in the `default` environment, because
their dependencies are not installed there. Make sure the `online` and
`xcube` environments are installed, and after a change that affects a fix or
recipe that the integration tests use, run them in both. They take about 5
minutes in `online` and 18 minutes in `xcube`, and need up to 6 GB of
memory. Select the tests of the affected datasets with `-k` while working
on a change, and run all of them before committing:

```bash
pixi run -e online pytest tests/integration
pixi run -e xcube pytest tests/integration
```

Each environment skips the tests that need the other one, and `online`
skips the Open Data Portal datasets, which only xcube-cci can open, while
`xcube` skips the recipe output tests of the zarr and Kerchunk datasets,
which `online` runs with all checkers. Check that the tests you expect to
run pass and are not skipped.

The integration tests only use the first few time steps of the Kerchunk
and Open Data Portal datasets. After adding a dataset or changing a fix or
recipe step that affects the time coordinate, also run them with
`--full-time-axis` on the affected datasets, selected with `-k`, e.g.
`-k WATERVAPOUR.day`.

### Memory use

The datasets are opened lazily, and some are tens of GB, so a fix that
loads data eagerly, e.g. with `np.zeros(data.shape)`, can use all the memory
of the machine. Keep the data of fixes lazy, and run the integration tests
and any script that opens the real data under a memory cap, so that the
process is killed instead of the machine running out of memory. On Linux:

```bash
systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0 \
    pixi run -e online pytest tests/integration
```

Use 4G for the unit tests. Exit code 137 means the process went over the
cap: treat it as a bug to investigate, not as a reason to raise the cap.
Run one integration run at a time, in the background: each can use up to
the cap. The pixi environments set `MALLOC_ARENA_MAX=2`, which stops the
memory use of long runs from creeping up.

### Other notes

- The CEDA server is sometimes unreliable: Kerchunk cases can fail with
  `ReferenceNotReachable` or `FSTimeoutError`. Rerun them before
  investigating.
- The Open Data Portal datasets only get the CF and CMIP7 checks by hand,
  since they need `xcube` and the checkers need `online`. Write the recipe
  output of each one to netCDF in `xcube`, with `open_fixed_dataset` and
  `compliance_checker.write_subset`, and check the files in `online` with
  `compliance_checker.run_checker` and `esmvalcore.cmor.check.cmor_check`.
- To show that a refactor leaves the output unchanged, dump the dimensions,
  attributes, encoding and sums of the first time steps of each case from
  `open_fixed_dataset` to JSON, for the new code and for a `git worktree`
  of the old commit, and compare them. NaN `_FillValue`s compare unequal.
