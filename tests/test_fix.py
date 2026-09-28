import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.add_tcwv_standard_name"


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_clean_dataset_has_no_findings(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_missing_standard_name_is_detected_and_fixed(
    tcwv_dataset: xr.Dataset,
) -> None:
    del tcwv_dataset["tcwv"].attrs["standard_name"]

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=True)
    assert preview.changed == 1
    assert "standard_name" not in tcwv_dataset["tcwv"].attrs

    result = woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=False)
    assert result.changed == 1
    assert (
        tcwv_dataset["tcwv"].attrs["standard_name"]
        == "atmosphere_mass_content_of_water_vapor"
    )
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)
