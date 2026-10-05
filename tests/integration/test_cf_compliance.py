from pathlib import Path

import pytest

from .esa_cci_data import CASES, Case, open_fixed_dataset

pytest.importorskip("s3fs")
netcdf4 = pytest.importorskip("netCDF4")
suite = pytest.importorskip("compliance_checker.suite")
cf = pytest.importorskip("compliance_checker.cf.cf")

CHECKER = "cf:1.11"


@pytest.mark.parametrize("case", CASES, ids=[c.short_name for c in CASES])
def test_complies_with_cf_conventions(case: Case, tmp_path: Path) -> None:
    dataset = open_fixed_dataset(case)
    # The compliance checker only reads netCDF files, so write a small part
    # of the dataset, around the Dutch coast to cover both land and sea.
    subset = dataset.isel(time=slice(0, 2)).sel(
        lat=slice(51.5, 53.0),
        lon=slice(3.0, 6.0),
    )
    assert all(size > 1 for size in subset.sizes.values())
    # Coordinates cannot have missing values, but xarray writes a _FillValue
    # for floating point variables, unless the encoding says otherwise.
    for name in list(subset.coords):
        for var in (name, subset[name].attrs.get("bounds")):
            if var in subset.variables:
                subset[var].encoding["_FillValue"] = None
    path = tmp_path / f"{case.short_name}.nc"
    subset.to_netcdf(path)

    check_suite = suite.CheckSuite()
    # Only load the CF checker, the other checkers include deprecated ones.
    check_suite.checkers = {CHECKER: cf.CF1_11Check}
    with netcdf4.Dataset(path) as ds:
        results = check_suite.run_all(ds, [CHECKER])
    groups, exceptions = results[CHECKER]
    assert not exceptions

    report = check_suite.build_structure(CHECKER, groups, str(path))
    failures = [
        message
        for priority in ("high", "medium", "low")
        for result in report[f"{priority}_priorities"]
        if result.value[0] < result.value[1]
        for message in result.msgs
    ]
    assert not failures
