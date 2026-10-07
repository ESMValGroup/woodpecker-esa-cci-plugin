import numpy as np
import pytest
import woodpecker
import xarray as xr
from pydantic import ValidationError
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.set_data_types"
OPTIONS = {
    FIX_ID: {"data_types": {"tcwv": "float64", "lat_bnds": "float32"}},
}


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_invalid_data_type_raises() -> None:
    fix = FixFunctionRegistry.instantiate(FIX_ID)

    with pytest.raises(ValidationError, match="'real' is not a data type"):
        fix.configure({"data_types": {"tcwv": "real"}})


def test_missing_variable_raises(tcwv_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"data_types": {"prw": "float32"}}}

    with pytest.raises(ValueError, match="prw: it does not exist"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


def test_data_types_are_set(tcwv_dataset: xr.Dataset) -> None:
    tcwv_dataset["tcwv"].encoding["dtype"] = np.dtype("int16")
    tcwv_dataset["lat_bnds"] = tcwv_dataset["lat_bnds"].astype("float64")
    original = tcwv_dataset.copy(deep=True)

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        "tcwv has data type float32, expected float64",
        "lat_bnds has data type float64, expected float32",
    ]

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert tcwv_dataset["tcwv"].dtype == np.float32

    result = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert tcwv_dataset["tcwv"].dtype == np.float64
    assert tcwv_dataset["lat_bnds"].dtype == np.float32
    assert "dtype" not in tcwv_dataset["tcwv"].encoding
    assert tcwv_dataset["tcwv"].attrs == original["tcwv"].attrs
    np.testing.assert_array_equal(tcwv_dataset["tcwv"], original["tcwv"])
    # The data stays lazy.
    assert tcwv_dataset["tcwv"].chunks is not None
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
