import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.add_scalar_coordinate"
ATTRIBUTES = {"standard_name": "radiation_wavelength", "units": "nm"}
OPTIONS = {
    FIX_ID: {
        "coordinates": {
            "wavelength": {"value": 550, "attributes": ATTRIBUTES},
        },
    },
}


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_coordinate_is_added(tcwv_dataset: xr.Dataset) -> None:
    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        (
            "wavelength is missing or differs from the expected scalar "
            "coordinate with value 550"
        ),
    ]

    preview = woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "wavelength" not in tcwv_dataset

    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    wavelength = tcwv_dataset.coords["wavelength"]
    assert wavelength.dims == ()
    assert wavelength.dtype == np.float64
    assert float(wavelength) == 550
    assert wavelength.attrs == ATTRIBUTES
    # The data variables get the scalar coordinate.
    assert "wavelength" in tcwv_dataset["tcwv"].coords
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    "coordinate",
    [
        xr.Variable((), np.float32(550), attrs=ATTRIBUTES),
        xr.Variable((), np.float64(500), attrs=ATTRIBUTES),
        xr.Variable((), np.float64(550), attrs={"units": "nm"}),
    ],
    ids=["data_type", "value", "attributes"],
)
def test_wrong_coordinate_is_corrected(
    tcwv_dataset: xr.Dataset, coordinate: xr.Variable
) -> None:
    coordinate.attrs["long_name"] = "Wavelength"
    tcwv_dataset.coords["wavelength"] = coordinate

    assert woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)
    woodpecker.apply(
        tcwv_dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    wavelength = tcwv_dataset.coords["wavelength"]
    assert wavelength.dtype == np.float64
    assert float(wavelength) == 550
    # Other attributes are kept.
    assert wavelength.attrs == {**ATTRIBUTES, "long_name": "Wavelength"}


def test_existing_variable_raises(tcwv_dataset: xr.Dataset) -> None:
    options = {
        FIX_ID: {
            "coordinates": {"tcwv": {"value": 1, "attributes": ATTRIBUTES}},
        },
    }

    with pytest.raises(ValueError, match="a variable with that name exists"):
        woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=options)


def test_invalid_options_raise() -> None:
    fix = FixFunctionRegistry.instantiate(FIX_ID)

    with pytest.raises(ValueError, match="value"):
        fix.configure({"coordinates": {"wavelength": {"attributes": {}}}})
