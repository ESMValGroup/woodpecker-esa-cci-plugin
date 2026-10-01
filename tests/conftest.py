import pytest
import xarray as xr

from .synthetic_data import make_tcwv_dataset


@pytest.fixture
def tcwv_dataset() -> xr.Dataset:
    """Return a small ESA CCI water vapour dataset as loaded with xcube."""
    return make_tcwv_dataset()
