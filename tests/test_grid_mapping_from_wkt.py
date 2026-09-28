import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.grid_mapping_from_wkt"
OPTIONS = {FIX_ID: {"variable": "crs", "wkt_attribute": "wkt"}}
WKT = (
    'GEOGCS["WGS84(DD)", DATUM["WGS84", '
    'SPHEROID["WGS84", 6378137.0, 298.257223563]], '
    'PRIMEM["Greenwich", 0.0], UNIT["degree", 0.017453292519943295], '
    'AXIS["Geodetic longitude", EAST], AXIS["Geodetic latitude", NORTH]]'
)


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    tcwv_dataset["crs"] = xr.DataArray(0, attrs={"wkt": WKT})
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_invalid_option_raises(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variable": ["crs"], "wkt_attribute": "wkt"}}

    with pytest.raises(TypeError, match="variable option"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_wkt_is_converted_to_cf(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert dataset["crs"].attrs == {"wkt": WKT}

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    attrs = dataset["crs"].attrs
    assert "wkt" not in attrs
    assert attrs["crs_wkt"].startswith('GEOGCRS["WGS84(DD)"')
    assert attrs["grid_mapping_name"] == "latitude_longitude"
    assert attrs["semi_major_axis"] == 6378137.0
    assert attrs["inverse_flattening"] == 298.257223563
    assert attrs["longitude_of_prime_meridian"] == 0.0
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
