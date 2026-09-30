import numpy as np
import pytest
import woodpecker
import xarray as xr

RECIPE_ID = "esa_cci.water_vapour"


@pytest.mark.parametrize(
    "recipe_id",
    [RECIPE_ID, "esa_cci.sea_surface_temperature"],
)
def test_recipe_is_discovered_from_package(recipe_id: str) -> None:
    recipe = woodpecker.recipe.get(recipe_id)

    assert recipe.id == recipe_id


def test_recipe_fixes_dataset(tcwv_dataset: xr.Dataset) -> None:
    recipe = woodpecker.recipe.get(RECIPE_ID)
    tcwv_dataset["tcwv"].attrs["units"] = "g m-2"
    original = tcwv_dataset.copy(deep=True)

    findings = woodpecker.recipe.check(tcwv_dataset, recipe)
    assert set(findings.fix_ids) == {
        "esa_cci.grid_mapping_from_wkt",
        "esa_cci.select_variables",
        "esa_cci.set_attributes",
        "esa_cci.convert_units",
        "woodpecker.rename_variables",
        "woodpecker.ensure_latitude_is_increasing",
        "esa_cci.normalize_longitude",
    }

    woodpecker.recipe.apply(tcwv_dataset, recipe, dry_run=False)

    assert set(tcwv_dataset.data_vars) == {
        "prw",
        "stdv",
        "num_obs",
        "crs",
        "lat_bnds",
        "lon_bnds",
        "time_bnds",
    }
    # The real dataset is too large to load, so the data must stay lazy.
    assert tcwv_dataset["prw"].chunks is not None
    prw_attrs = tcwv_dataset["prw"].attrs
    assert {
        key: prw_attrs[key]
        for key in (
            "standard_name",
            "long_name",
            "units",
            "cell_methods",
            "grid_mapping",
        )
    } == {
        "standard_name": "atmosphere_mass_content_of_water_vapor",
        "long_name": "Water Vapor Path",
        "units": "kg m-2",
        "cell_methods": "area: time: mean",
        "grid_mapping": "crs",
    }
    np.testing.assert_allclose(prw_attrs["valid_range"], [0.0, 0.07])
    crs_attrs = tcwv_dataset["crs"].attrs
    assert "standard_name" not in crs_attrs
    assert "wkt" not in crs_attrs
    assert crs_attrs["grid_mapping_name"] == "latitude_longitude"

    # Latitude is increasing and longitude is in the range [0, 360).
    expected = (
        original["tcwv"]
        .isel(lat=slice(None, None, -1))
        .roll(lon=original.sizes["lon"] // 2)
    )
    np.testing.assert_allclose(tcwv_dataset["prw"], expected * 1e-3)
    np.testing.assert_allclose(
        tcwv_dataset["lat"], original["lat"].to_numpy()[::-1]
    )
    np.testing.assert_allclose(
        tcwv_dataset["lon"], np.arange(22.5, 360.0, 45.0)
    )
    np.testing.assert_allclose(
        tcwv_dataset["lon_bnds"][:, 0], np.arange(0.0, 360.0, 45.0)
    )
    for name in ("lon", "lon_bnds"):
        assert tcwv_dataset[name].attrs["valid_range"] == [0.0, 360.0]
