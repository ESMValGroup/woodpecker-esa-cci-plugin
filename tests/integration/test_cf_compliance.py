from pathlib import Path

import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

pytest.importorskip("s3fs")
cf = pytest.importorskip("compliance_checker.cf.cf")
compliance = pytest.importorskip("tests.integration.compliance_checker")


@pytest.mark.parametrize(
    "decode_times", [True, False], ids=["decoded", "not_decoded"]
)
@pytest.mark.parametrize("case", CASES, ids=[c.variable_id for c in CASES])
def test_complies_with_cf_conventions(
    case: Case,
    decode_times: bool,  # noqa: FBT001
    tmp_path: Path,
) -> None:
    dataset = open_fixed_dataset(case, decode_times=decode_times)
    path = tmp_path / f"{case.variable_id}.nc"
    compliance.write_subset(dataset, path)

    assert not compliance.run_checker(path, "cf:1.11", cf.CF1_11Check)
