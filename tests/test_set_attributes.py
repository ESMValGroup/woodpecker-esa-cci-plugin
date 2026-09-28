import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.set_attributes"
ATTRIBUTES = {
    "standard_name": "atmosphere_mass_content_of_water_vapor",
    "long_name": "Water Vapor Path",
}
OPTIONS = {FIX_ID: {"attributes": {"tcwv": ATTRIBUTES}}}


@pytest.fixture
def clean_dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset["tcwv"].attrs.update(ATTRIBUTES)
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_clean_dataset_has_no_findings(clean_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID, options=OPTIONS)


def test_unconfigured_fix_does_nothing(clean_dataset: xr.Dataset) -> None:
    del clean_dataset["tcwv"].attrs["standard_name"]

    assert not woodpecker.check(clean_dataset, fixes=FIX_ID)


def test_invalid_option_raises(clean_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"attributes": {"tcwv": "Water Vapor Path"}}}

    with pytest.raises(TypeError, match="attributes option"):
        woodpecker.check(clean_dataset, fixes=FIX_ID, options=options)


@pytest.mark.parametrize("value", [None, "tcwv"])
def test_attributes_are_detected_and_fixed(
    clean_dataset: xr.Dataset,
    value: str | None,
) -> None:
    attrs = clean_dataset["tcwv"].attrs
    for key in ATTRIBUTES:
        if value is None:
            del attrs[key]
        else:
            attrs[key] = value

    findings = woodpecker.check(clean_dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,) * len(ATTRIBUTES)

    preview = woodpecker.apply(
        clean_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert all(attrs.get(key) == value for key in ATTRIBUTES)

    result = woodpecker.apply(
        clean_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert {key: attrs[key] for key in ATTRIBUTES} == ATTRIBUTES
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID, options=OPTIONS)


def test_attribute_set_to_none_is_removed(clean_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"attributes": {"tcwv": {"long_name": None}}}}

    findings = woodpecker.check(clean_dataset, fixes=FIX_ID, options=options)
    assert findings.fix_ids == (FIX_ID,)

    woodpecker.apply(
        clean_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    assert "long_name" not in clean_dataset["tcwv"].attrs
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID, options=options)
