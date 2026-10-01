import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

from woodpecker_esa_cci_plugin.remove_attributes import RANGE_ATTRIBUTES

FIX_ID = "esa_cci.remove_attributes"
OPTIONS = {FIX_ID: {"attributes": list(RANGE_ATTRIBUTES)}}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    """Add range attributes to a data variable, coordinate and bounds."""
    tcwv_dataset["tcwv"].attrs.update(
        actual_range=[0.01, 69.96],
        valid_range=[0.0, 70.0],
    )
    tcwv_dataset["lat"].attrs.update(valid_min=-90.0, valid_max=90.0)
    tcwv_dataset["lon_bnds"].attrs["valid_range"] = [-180.0, 180.0]
    return tcwv_dataset


def _range_attributes(dataset: xr.Dataset) -> dict[str, list[str]]:
    return {
        str(name): sorted(set(RANGE_ATTRIBUTES) & set(variable.attrs))
        for name, variable in dataset.variables.items()
        if set(RANGE_ATTRIBUTES) & set(variable.attrs)
    }


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    ("attributes", "error", "match"),
    [
        ("valid_range", TypeError, "sequence of attribute names"),
        ([], ValueError, "must not be empty"),
    ],
)
def test_invalid_option_raises(
    dataset: xr.Dataset,
    attributes: object,
    error: type[Exception],
    match: str,
) -> None:
    options = {FIX_ID: {"attributes": attributes}}

    with pytest.raises(error, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_attributes_are_removed(dataset: xr.Dataset) -> None:
    before = _range_attributes(dataset)
    assert {"tcwv", "lat", "lon", "lon_bnds"} <= set(before)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,) * len(before)

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert _range_attributes(dataset) == before

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert not _range_attributes(dataset)
    assert dataset["tcwv"].attrs["units"] == "kg/m2"
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
