"""Check that the synthetic datasets still look like the real datasets."""

from typing import Any

import numpy as np
import pytest
import xarray as xr

from tests.unit.synthetic_esa_cci_data import make_tcwv_dataset

xcube_store = pytest.importorskip("xcube.core.store")

DATA_ID = "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr"
# Encoding keys that affect how the data is decoded and written.
ENCODING_KEYS = ("dtype", "_FillValue", "units", "calendar")


@pytest.fixture(scope="module")
def real_dataset() -> xr.Dataset:
    dataset: xr.Dataset = xcube_store.new_data_store("ccizarr").open_data(
        DATA_ID
    )
    return dataset


def _encoding(variable: xr.Variable) -> dict[str, Any]:
    return {
        k: variable.encoding[k]
        for k in ENCODING_KEYS
        if k in variable.encoding
    }


def test_variables_match(real_dataset: xr.Dataset) -> None:
    synthetic_dataset = make_tcwv_dataset()
    assert set(synthetic_dataset.data_vars) == set(real_dataset.data_vars)
    assert set(synthetic_dataset.coords) == set(real_dataset.coords)
    for name, real in real_dataset.variables.items():
        synthetic = synthetic_dataset[name].variable
        assert synthetic.dims == real.dims, name
        assert synthetic.dtype == real.dtype, name
        np.testing.assert_equal(synthetic.attrs, real.attrs, err_msg=name)
        np.testing.assert_equal(
            _encoding(synthetic), _encoding(real), err_msg=name
        )


def test_global_attributes_match(real_dataset: xr.Dataset) -> None:
    assert make_tcwv_dataset().attrs == real_dataset.attrs


def test_grid_orientation_matches(real_dataset: xr.Dataset) -> None:
    synthetic_dataset = make_tcwv_dataset()
    for dataset in (synthetic_dataset, real_dataset):
        lat = dataset["lat"].to_numpy()
        lon = dataset["lon"].to_numpy()
        lat_bnds = dataset["lat_bnds"][:2].to_numpy()
        lon_bnds = dataset["lon_bnds"][:2].to_numpy()
        assert lat[0] > lat[-1]
        assert lon[0] < lon[-1]
        assert lon[0] < 0
        assert (lat_bnds[:, 0] > lat_bnds[:, 1]).all()
        assert (lon_bnds[:, 0] < lon_bnds[:, 1]).all()
    assert synthetic_dataset["crs"].item() == real_dataset["crs"].item()
