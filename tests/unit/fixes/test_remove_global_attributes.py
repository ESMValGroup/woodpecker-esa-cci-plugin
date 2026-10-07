import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.remove_global_attributes"
OPTIONS = {FIX_ID: {"attributes": ["comment", "history"]}}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset.attrs["comment"] = ""
    tcwv_dataset.attrs.pop("history", None)
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_attributes_are_removed(dataset: xr.Dataset) -> None:
    title = dataset.attrs["title"]

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    # Attributes that do not exist are ignored.
    assert messages == ["dataset has global attribute comment"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert dataset.attrs["comment"] == ""

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert "comment" not in dataset.attrs
    assert dataset.attrs["title"] == title
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
