import pytest
import woodpecker
import xarray as xr
from pyproj.exceptions import CRSError
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.grid_mapping_from_wkt"
OPTIONS = {FIX_ID: {"variable": "crs", "wkt_attribute": "wkt"}}


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_invalid_option_raises(tcwv_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variable": ["crs"], "wkt_attribute": "wkt"}}

    with pytest.raises(TypeError, match="variable option"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


def test_wkt_is_converted_to_cf(tcwv_dataset: xr.Dataset) -> None:
    original = dict(tcwv_dataset["crs"].attrs)

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert tcwv_dataset["crs"].attrs == original

    result = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    attrs = tcwv_dataset["crs"].attrs
    assert "wkt" not in attrs
    assert attrs["crs_wkt"].startswith('GEOGCRS["WGS84(DD)"')
    assert attrs["grid_mapping_name"] == "latitude_longitude"
    assert attrs["semi_major_axis"] == 6378137.0
    assert attrs["inverse_flattening"] == 298.257223563
    assert attrs["longitude_of_prime_meridian"] == 0.0


def test_invalid_wkt_is_kept(tcwv_dataset: xr.Dataset) -> None:
    tcwv_dataset["crs"].attrs["wkt"] = "not a WKT string"

    with pytest.raises(CRSError):
        woodpecker.apply(
            tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
        )
    assert tcwv_dataset["crs"].attrs["wkt"] == "not a WKT string"


@pytest.mark.parametrize(
    ("options", "match"),
    [
        ({"variable": "crs"}, "must both be set"),
        ({"variable": "grid", "wkt_attribute": "wkt"}, "grid: it does not"),
        (
            {"variable": "crs", "wkt_attribute": "spatial_ref"},
            "no spatial_ref",
        ),
    ],
)
def test_missing_wkt_raises(
    tcwv_dataset: xr.Dataset,
    options: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options={FIX_ID: options})
