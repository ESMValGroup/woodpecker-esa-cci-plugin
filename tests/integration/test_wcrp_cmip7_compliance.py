import shutil
import subprocess
from pathlib import Path

import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

pytest.importorskip("s3fs")
toml = pytest.importorskip("toml")
cmip7 = pytest.importorskip("plugins.cmip7.cmip7")
compliance = pytest.importorskip("tests.integration.compliance_checker")

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
# The versions of the vocabularies that the checker checks against.
VOCABULARIES = ("cmip7@2.4.1", "universe@3.2.7")
# The format of the time range at the end of CMIP7 file names.
TIME_RANGE_FORMATS = {"mon": "%Y%m", "day": "%Y%m%d"}


@pytest.fixture(scope="module")
def _vocabularies() -> None:
    """Install and activate the vocabularies, if they are not installed.

    The online environment stores them in .pixi/esgvoc.
    """
    esgvoc = shutil.which("esgvoc")
    assert esgvoc is not None
    subprocess.run([esgvoc, "use", *VOCABULARIES], check=True)  # noqa: S603


@pytest.fixture(scope="module")
def config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the CMIP7 checker configuration without the skipped checks."""
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


@pytest.mark.usefixtures("_vocabularies")
@pytest.mark.parametrize("case", CASES, ids=[c.variable_id for c in CASES])
def test_complies_with_cmip7(
    case: Case,
    config_dir: Path,
    tmp_path: Path,
) -> None:
    dataset = open_fixed_dataset(case)
    # The checker reads the time range from the file name.
    times = dataset.indexes["time"][:2]
    time_format = TIME_RANGE_FORMATS[dataset.attrs["frequency"]]
    time_range = "-".join(time.strftime(time_format) for time in times)
    path = tmp_path / f"{case.variable_id}_{time_range}.nc"
    compliance.write_subset(dataset, path)

    failures = compliance.run_checker(
        path,
        "wcrp_cmip7:1.0",
        cmip7.Cmip7ProjectCheck,
        options={"project_config_dir": str(config_dir)},
    )
    assert not failures
