import pytest
import woodpecker
import xarray as xr
from pydantic import ValidationError
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.fix_variable_references"
REFERENCES = {
    "grid_mapping": "crs",
    "ancillary_variables": "stdv num_obs tcwv_err",
}
OPTIONS = {FIX_ID: {"references": {"tcwv": REFERENCES}}}


@pytest.fixture
def clean_dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset["tcwv"].attrs.update(REFERENCES)
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_clean_dataset_has_no_findings(clean_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID, options=OPTIONS)
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID)


def test_configured_references_are_set(tcwv_dataset: xr.Dataset) -> None:
    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert sorted(messages) == [
        (
            "tcwv has ancillary_variables 'stdv num_obs', expected "
            "'stdv num_obs tcwv_err'"
        ),
        "tcwv has grid_mapping None, expected 'crs'",
    ]

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "grid_mapping" not in tcwv_dataset["tcwv"].attrs

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert all(
        tcwv_dataset["tcwv"].attrs[key] == value
        for key, value in REFERENCES.items()
    )
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


def test_empty_reference_is_removed(clean_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"references": {"tcwv": {"ancillary_variables": ""}}}}
    findings = woodpecker.check(clean_dataset, fixes=FIX_ID, options=options)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        ("tcwv has ancillary_variables 'stdv num_obs tcwv_err', expected ''"),
    ]

    woodpecker.apply(
        clean_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    assert "ancillary_variables" not in clean_dataset["tcwv"].attrs
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID, options=options)


def test_invalid_references_are_removed(clean_dataset: xr.Dataset) -> None:
    # Like the aerosol datasets in the Open Data Portal store, after xarray
    # moved the attribute to the encoding.
    clean_dataset["tcwv"].encoding["coordinates"] = "latitude longitude"
    # Keep the names that exist.
    clean_dataset["stdv"].attrs["ancillary_variables"] = "num_obs missing"
    clean_dataset["stdv"].attrs["cell_measures"] = (
        "area: missing volume: num_obs"
    )
    clean_dataset["tcwv_err"].attrs["grid_mapping"] = "missing"
    findings = woodpecker.check(clean_dataset, fixes=FIX_ID)
    messages = [finding["message"] for finding in findings.findings]
    assert sorted(messages) == [
        (
            "stdv refers to missing in its ancillary_variables attribute, "
            "which do not exist"
        ),
        (
            "stdv refers to missing in its cell_measures attribute, which "
            "do not exist"
        ),
        (
            "tcwv refers to latitude, longitude in its coordinates "
            "encoding, which do not exist"
        ),
        (
            "tcwv_err refers to missing in its grid_mapping attribute, "
            "which do not exist"
        ),
    ]

    preview = woodpecker.apply(clean_dataset, fixes=FIX_ID, dry_run=True)
    assert preview.changed == 1
    assert clean_dataset["tcwv_err"].attrs["grid_mapping"] == "missing"

    woodpecker.apply(clean_dataset, fixes=FIX_ID, dry_run=False)
    assert "coordinates" not in clean_dataset["tcwv"].encoding
    assert clean_dataset["stdv"].attrs["ancillary_variables"] == "num_obs"
    assert clean_dataset["stdv"].attrs["cell_measures"] == "volume: num_obs"
    assert "grid_mapping" not in clean_dataset["tcwv_err"].attrs
    assert not woodpecker.check(clean_dataset, fixes=FIX_ID)


def test_extended_grid_mapping_is_kept(clean_dataset: xr.Dataset) -> None:
    clean_dataset["tcwv"].attrs["grid_mapping"] = "crs: lat lon"

    assert not woodpecker.check(clean_dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    ("references", "message"),
    [
        (
            {"missing": {"grid_mapping": "crs"}},
            "Unable to set the references of missing: it does not exist",
        ),
        (
            {"tcwv": {"ancillary_variables": "stdv missing other"}},
            (
                "Unable to set the references of tcwv: missing, other do "
                "not exist"
            ),
        ),
    ],
)
def test_missing_variables_raise(
    tcwv_dataset: xr.Dataset,
    references: dict[str, dict[str, str]],
    message: str,
) -> None:
    options = {FIX_ID: {"references": references}}
    with pytest.raises(ValueError, match=message):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


@pytest.mark.parametrize(
    "references",
    [
        {},
        {"tcwv": {}},
        # xarray manages the coordinates attribute.
        {"tcwv": {"coordinates": "lat lon"}},
        {"tcwv": {"ancillary_variables": 1}},
    ],
)
def test_invalid_options_raise(
    tcwv_dataset: xr.Dataset, references: dict[str, object]
) -> None:
    options = {FIX_ID: {"references": references}}
    with pytest.raises(ValidationError):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)
