import numpy as np
import pytest
import woodpecker
import xarray as xr
from pint.errors import DimensionalityError
from woodpecker.fixes.registry import FixFunctionRegistry

from woodpecker_esa_cci_plugin.fixes.remove_attributes import RANGE_ATTRIBUTES

FIX_ID = "esa_cci.convert_units"
OPTIONS = {FIX_ID: {"units": {"tcwv": "kg m-2"}}}


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_missing_variable_raises(tcwv_dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"units": {"prw": "kg m-2"}}}

    with pytest.raises(ValueError, match="prw to kg m-2: it does not exist"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


def test_variable_without_units_raises(tcwv_dataset: xr.Dataset) -> None:
    del tcwv_dataset["tcwv"].attrs["units"]

    with pytest.raises(ValueError, match="tcwv to kg m-2: it has no units"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    ("units", "factor"),
    [("kg/m2", 1.0), ("g m-2", 1e-3), ("kg cm-2", 1e4)],
)
def test_units_are_converted(
    tcwv_dataset: xr.Dataset,
    units: str,
    factor: float,
) -> None:
    tcwv_dataset["tcwv"].attrs["units"] = units
    tcwv_dataset["tcwv"].encoding = {"dtype": "float32"}
    original = tcwv_dataset["tcwv"].copy()

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert tcwv_dataset["tcwv"].attrs["units"] == units

    result = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    tcwv = tcwv_dataset["tcwv"]
    # The range attributes are only removed when the values change.
    assert set(tcwv.attrs) == {
        key
        for key in original.attrs
        if factor == 1.0 or key not in RANGE_ATTRIBUTES
    }
    assert tcwv.attrs["units"] == "kg m-2"
    assert tcwv.dtype == original.dtype
    assert tcwv.encoding == {"dtype": "float32"}
    np.testing.assert_allclose(tcwv, original * factor, rtol=1e-6)
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


def test_incompatible_units_raise(tcwv_dataset: xr.Dataset) -> None:
    tcwv_dataset["tcwv"].attrs["units"] = "K"

    with pytest.raises(DimensionalityError):
        woodpecker.apply(
            tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
        )


@pytest.mark.parametrize(
    "encoding",
    [
        {"dtype": "int16", "scale_factor": 0.1, "_FillValue": -1},
        {"dtype": "int32", "_FillValue": -1},
    ],
)
def test_integer_encoding_is_removed(
    tcwv_dataset: xr.Dataset,
    encoding: dict[str, object],
) -> None:
    tcwv_dataset["tcwv"].attrs["units"] = "g m-2"
    tcwv_dataset["tcwv"].encoding = encoding

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert tcwv_dataset["tcwv"].encoding == {}


def test_range_attributes_are_removed(tcwv_dataset: xr.Dataset) -> None:
    tcwv_dataset["tcwv"].attrs.update(
        units="g m-2",
        actual_range=[10.0, 60000.0],
        valid_range=np.array([0.0, 80000.0]),
        valid_min=0,
        valid_max=80000,
    )

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert not set(RANGE_ATTRIBUTES) & set(tcwv_dataset["tcwv"].attrs)


def test_dimension_coordinate_and_bounds_are_converted(
    tcwv_dataset: xr.Dataset,
) -> None:
    lat = tcwv_dataset["lat"]
    lat.attrs["units"] = "km"
    lat.attrs["bounds"] = "lat_bnds"
    tcwv_dataset["lat_bnds"] = (
        ("lat", "nv"),
        np.column_stack([lat - 0.5, lat + 0.5]),
    )
    expected = lat.to_numpy() * 1000
    options = {FIX_ID: {"units": {"lat": "m"}}}

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=options
    )
    np.testing.assert_allclose(tcwv_dataset["lat"], expected)
    np.testing.assert_allclose(tcwv_dataset.indexes["lat"], expected)
    np.testing.assert_allclose(tcwv_dataset["lat_bnds"][:, 0], expected - 500)
    assert tcwv_dataset["lat"].attrs["units"] == "m"
    assert "units" not in tcwv_dataset["lat_bnds"].attrs
