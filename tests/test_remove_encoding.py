import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.remove_encoding"
PACKING_KEYS = [
    "_FillValue",
    "_Unsigned",
    "add_offset",
    "dtype",
    "missing_value",
    "scale_factor",
]
OPTIONS = {FIX_ID: {"keys": PACKING_KEYS}}
# Packed like the ESA CCI SST data.
PACKING = {
    "dtype": np.dtype("int16"),
    "scale_factor": 0.01,
    "add_offset": 0.0,
    "_FillValue": np.int16(-32768),
}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset["tcwv"].encoding = dict(PACKING, chunks=(1, 2, 4))
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_encoding_is_removed(dataset: xr.Dataset) -> None:
    original = {
        name: dict(variable.encoding)
        for name, variable in dataset.variables.items()
    }

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert "tcwv has encoding _FillValue, add_offset, dtype, scale_factor" in (
        messages
    )

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert dataset["tcwv"].encoding == original["tcwv"]

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    # Encoding that is not configured, such as chunks, is kept.
    assert dataset["tcwv"].encoding == {"chunks": (1, 2, 4)}
    for name in ("lat", "lon_bnds", "crs"):
        assert "dtype" not in dataset[name].encoding
    # The encoding of decoded times defines how they are written.
    for name in ("time", "time_bnds"):
        assert dataset[name].encoding == original[name]
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_changed_values_are_written_correctly(dataset: xr.Dataset) -> None:
    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    # Values that do not fit the original packing, changed in place, which
    # keeps the encoding.
    variable = dataset["tcwv"].variable
    variable *= 1000

    encoded = xr.conventions.encode_cf_variable(variable, name="tcwv")
    decoded = xr.conventions.decode_cf_variable("tcwv", encoded)
    np.testing.assert_allclose(decoded, variable)
