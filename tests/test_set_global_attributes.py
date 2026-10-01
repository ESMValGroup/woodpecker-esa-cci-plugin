import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.set_global_attributes"
OPTIONS = {
    FIX_ID: {
        "rename": {"naming-authority": "naming_authority"},
        "attributes": {"Conventions": "CF-1.11", "comment": None},
    }
}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset.attrs.update(
        {"naming-authority": "ESACCI", "Conventions": "CF-1.7", "comment": ""}
    )
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    ("options", "error", "match"),
    [
        ({"attributes": "CF-1.11"}, TypeError, "attributes option must be"),
        ({"rename": {}}, ValueError, "rename option must not be empty"),
        (
            {"rename": {"title": "Conventions"}},
            ValueError,
            "Conventions already exists",
        ),
        (
            {"rename": {"naming_authority": "authority"}},
            ValueError,
            "naming_authority does not exist",
        ),
    ],
)
def test_invalid_option_raises(
    dataset: xr.Dataset,
    options: dict[str, object],
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options={FIX_ID: options})


def test_attributes_are_renamed_and_set(dataset: xr.Dataset) -> None:
    original = dict(dataset.attrs)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,) * 3

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    for key in ("naming-authority", "Conventions", "comment"):
        assert dataset.attrs[key] == original[key]

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert "naming-authority" not in dataset.attrs
    assert dataset.attrs["naming_authority"] == "ESACCI"
    assert dataset.attrs["Conventions"] == "CF-1.11"
    assert "comment" not in dataset.attrs
    assert dataset.attrs["title"] == original["title"]
    # Renamed attributes are not renamed again.
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_renamed_attribute_is_set(dataset: xr.Dataset) -> None:
    options = {
        FIX_ID: {
            "rename": {"naming-authority": "naming_authority"},
            "attributes": {"naming_authority": "ESA CCI"},
        }
    }

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=options)
    assert dataset.attrs["naming_authority"] == "ESA CCI"
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=options)
