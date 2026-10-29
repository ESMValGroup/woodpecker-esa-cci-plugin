"""Check the output of the recipes for the real datasets.

Each dataset is opened, fixed and written to a small netCDF file once, and
then checked with all checkers that are installed. The fixtures are module
scoped and parametrized by the case, so pytest runs all checks of one case
before opening the next, and only one dataset is in memory at a time.
"""

import shutil
import subprocess
import warnings
from collections.abc import Iterator
from pathlib import Path

import dask
import pytest
import xarray as xr

from .esa_cci_data import (
    CASES,
    TIME_STEPS,
    Case,
    open_fixed_dataset,
)

pytest.importorskip("s3fs")
compliance = pytest.importorskip("tests.integration.compliance_checker")
iris_conversion = pytest.importorskip("tests.integration.iris_conversion")

# Checks of how CMIP7 data is stored and published, which do not apply to
# the recipe output: the file format, compression, directory structure and
# file name, and the global attributes, which describe CMIP7 simulations.
SKIPPED_CONFIG_FILES = ("file.toml", "drs.toml", "global_attributes.toml")
# Variable attributes that define how the values are stored on disk, and
# cell_measures, because ESA CCI datasets do not provide cell areas.
SKIPPED_ATTRIBUTES = (
    "cell_measures",
    "fill_value",
    "missing_value",
    "deflated_level",
    "scale_factor",
    "add_offset",
)
# The versions of the vocabularies that the CMIP7 checker checks against.
VOCABULARIES = ("cmip7@2.4.1", "universe@3.2.7")
# The format of the time range at the end of CMIP7 file names.
TIME_RANGE_FORMATS = {"mon": "%Y%m", "day": "%Y%m%d"}


@pytest.fixture(scope="module", params=CASES, ids=[c.id for c in CASES])
def case(request: pytest.FixtureRequest) -> Case:
    result: Case = request.param
    return result


@pytest.fixture(scope="module")
def _dask_scheduler(case: Case) -> Iterator[None]:
    """Read the Kerchunk and Open Data Portal data in a single thread.

    The xcube-cci Open Data Portal store shares an asyncio lock between the
    event loops of all datasets. When threads wait for it, it is bound to
    the event loop of one dataset, and reading another dataset raises
    "RuntimeError: ... is bound to a different event loop". The server of
    the files that the Kerchunk references point to sometimes disconnects
    when several threads read from it at the same time.
    """
    if case.store == "ccizarr":
        yield
        return
    with dask.config.set(scheduler="synchronous"):
        yield


@pytest.fixture(scope="module")
def fixed_dataset(
    case: Case,
    full_time_axis: bool,  # noqa: FBT001
    _dask_scheduler: None,
) -> xr.Dataset:
    return open_fixed_dataset(case, full_time_axis=full_time_axis)


@pytest.fixture(scope="module")
def subset_path(
    case: Case,
    fixed_dataset: xr.Dataset,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Return a netCDF file with a small part of the fixed dataset.

    It is named like a CMIP7 file, because the CMIP7 checker reads the time
    range from the file name.
    """
    # The first and last time step in the file.
    times = fixed_dataset.indexes["time"][[0, TIME_STEPS - 1]]
    time_format = TIME_RANGE_FORMATS[fixed_dataset.attrs["frequency"]]
    time_range = "-".join(time.strftime(time_format) for time in times)
    path = tmp_path_factory.mktemp("decoded") / (
        f"{case.variable_id}_{time_range}.nc"
    )
    compliance.write_subset(fixed_dataset, path)
    return path


@pytest.fixture(scope="module")
def not_decoded_subset_path(
    case: Case,
    full_time_axis: bool,  # noqa: FBT001
    _dask_scheduler: None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Return a netCDF file with a small part of the fixed dataset.

    The dataset is opened without decoding the times, which the recipes
    support too.
    """
    dataset = open_fixed_dataset(
        case,
        decode_times=False,
        full_time_axis=full_time_axis,
    )
    path = tmp_path_factory.mktemp("not_decoded") / f"{case.variable_id}.nc"
    compliance.write_subset(dataset, path)
    return path


@pytest.fixture(scope="module")
def _vocabularies() -> None:
    """Install and activate the vocabularies, if they are not installed.

    The online environment stores them in .pixi/esgvoc.
    """
    esgvoc = shutil.which("esgvoc")
    if esgvoc is None:
        pytest.skip("The CMIP7 checker is not installed")
    subprocess.run([esgvoc, "use", *VOCABULARIES], check=True)  # noqa: S603


@pytest.fixture(scope="module")
def cmip7_config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the CMIP7 checker configuration without the skipped checks."""
    toml = pytest.importorskip("toml")
    cmip7 = pytest.importorskip("plugins.cmip7.cmip7")
    source = Path(cmip7.__file__).parent / "config" / "wcrp"
    target = tmp_path_factory.mktemp("wcrp_cmip7")
    shutil.copytree(source, target, dirs_exist_ok=True)
    for name in SKIPPED_CONFIG_FILES:
        # Empty, because the checker warns about missing files.
        (target / name).write_text("", encoding="utf-8")
    path = target / "geophysical_variable.toml"
    config = toml.loads(path.read_text(encoding="utf-8"))
    for name in SKIPPED_ATTRIBUTES:
        del config["variable"]["attributes"][name]
    path.write_text(toml.dumps(config), encoding="utf-8")
    return target


def test_complies_with_cf_conventions(subset_path: Path) -> None:
    cf = pytest.importorskip("compliance_checker.cf.cf")

    failures = compliance.run_checker(subset_path, "cf:1.11", cf.CF1_11Check)
    assert not failures


def test_complies_with_cf_conventions_without_decoding_times(
    not_decoded_subset_path: Path,
) -> None:
    cf = pytest.importorskip("compliance_checker.cf.cf")

    failures = compliance.run_checker(
        not_decoded_subset_path, "cf:1.11", cf.CF1_11Check
    )
    assert not failures


@pytest.mark.usefixtures("_vocabularies")
def test_complies_with_cmip7(
    subset_path: Path,
    cmip7_config_dir: Path,
) -> None:
    cmip7 = pytest.importorskip("plugins.cmip7.cmip7")

    failures = compliance.run_checker(
        subset_path,
        "wcrp_cmip7:1.0",
        cmip7.Cmip7ProjectCheck,
        options={"project_config_dir": str(cmip7_config_dir)},
    )
    assert not failures


def test_loads_with_iris_without_warnings(
    case: Case,
    fixed_dataset: xr.Dataset,
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cubes = iris_conversion.dataset_to_cubes(fixed_dataset)

    assert len(cubes) == 1
    assert cubes[0].var_name == case.variable_id


def test_uncertainties_have_the_units_of_the_variable(
    case: Case,
    fixed_dataset: xr.Dataset,
) -> None:
    variable = fixed_dataset[case.variable_id]
    names = variable.attrs.get("ancillary_variables", "").split()
    if not names:
        pytest.skip(f"{case.variable_id} has no uncertainties")
    for name in names:
        attrs = fixed_dataset[name].attrs
        # Counts, such as the number of observations, are dimensionless.
        if attrs["units"] != "1":
            assert attrs["units"] == variable.attrs["units"], name


def test_passes_cmip7_cmor_check(
    case: Case,
    fixed_dataset: xr.Dataset,
) -> None:
    # Importing the configuration loads the CMOR tables.
    pytest.importorskip("esmvalcore.config")
    esmvalcore_check = pytest.importorskip("esmvalcore.cmor.check")

    cubes = iris_conversion.dataset_to_cubes(fixed_dataset)
    assert len(cubes) == 1
    cube = cubes[0]
    assert cube.var_name == case.variable_id
    # Iris changes the latitude and longitude units to degrees, so restore
    # them from the dataset like the ESMValCore loader does.
    for coord in cube.coords(axis="X") + cube.coords(axis="Y"):
        coord.units = fixed_dataset[coord.var_name].attrs["units"]

    # The recipe stores the CMIP7 variable in the global attributes.
    attrs = cube.attributes
    esmvalcore_check.cmor_check(
        cube,
        cmor_table="CMIP7",
        mip=attrs["realm"],
        short_name=attrs["variable_id"],
        branding_suffix=attrs["branded_variable"].removeprefix(
            f"{attrs['variable_id']}_"
        ),
        frequency=attrs["frequency"],
    )
