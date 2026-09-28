import pytest
import xarray as xr
from woodpecker.testing import make_cmip7


@pytest.fixture
def tcwv_dataset() -> xr.Dataset:
    """Return a small ESA CCI-like water vapour dataset without problems."""
    dataset: xr.Dataset = make_cmip7(
        variable="prw",
        rename_vars={"prw": "tcwv"},
    )
    dataset["tcwv"].attrs["standard_name"] = (
        "atmosphere_mass_content_of_water_vapor"
    )
    dataset["tcwv"].attrs["units"] = "kg/m2"
    return dataset
