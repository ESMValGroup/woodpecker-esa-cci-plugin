import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.remove_invalid_coordinates"


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_valid_dataset_is_unchanged(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_invalid_coordinates_are_removed(tcwv_dataset: xr.Dataset) -> None:
    # Like the aerosol datasets in the Open Data Portal store, after xarray
    # moved the attribute to the encoding.
    tcwv_dataset["tcwv"].encoding["coordinates"] = "latitude longitude"
    # Keep the coordinates that exist.
    tcwv_dataset["stdv"].attrs["coordinates"] = "latitude lat"
    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID)
    messages = [finding["message"] for finding in findings.findings]
    assert sorted(messages) == [
        (
            "stdv refers to coordinates latitude in its coordinates "
            "attribute, which do not exist"
        ),
        (
            "tcwv refers to coordinates latitude, longitude in its "
            "coordinates encoding, which do not exist"
        ),
    ]

    preview = woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=True)
    assert preview.changed == 1
    assert tcwv_dataset["tcwv"].encoding["coordinates"] == "latitude longitude"
    assert tcwv_dataset["stdv"].attrs["coordinates"] == "latitude lat"

    woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=False)
    assert "coordinates" not in tcwv_dataset["tcwv"].encoding
    assert tcwv_dataset["stdv"].attrs["coordinates"] == "lat"
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)
