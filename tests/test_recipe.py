import numpy as np
import woodpecker
import xarray as xr
from test_grid_mapping_from_wkt import WKT

RECIPE_ID = "esa_cci.water_vapour"


def test_recipe_is_discovered_from_package() -> None:
    recipe = woodpecker.recipe.get(RECIPE_ID)

    assert recipe.id == RECIPE_ID


def test_recipe_fixes_dataset(tcwv_dataset: xr.Dataset) -> None:
    recipe = woodpecker.recipe.get(RECIPE_ID)
    dataset = tcwv_dataset.isel(lat=slice(None, None, -1))
    dataset["tcwv"].attrs["units"] = "g m-2"
    del dataset["tcwv"].attrs["standard_name"]
    dataset["crs"] = xr.DataArray(
        0,
        attrs={"standard_name": "coordinate reference system", "wkt": WKT},
    )
    original = dataset["tcwv"].isel(lat=slice(None, None, -1)).copy()

    findings = woodpecker.recipe.check(dataset, recipe)
    assert set(findings.fix_ids) == {
        "esa_cci.grid_mapping_from_wkt",
        "esa_cci.select_variables",
        "esa_cci.set_attributes",
        "esa_cci.convert_units",
        "woodpecker.rename_variables",
        "woodpecker.ensure_latitude_is_increasing",
    }

    woodpecker.recipe.apply(dataset, recipe, dry_run=False)

    assert "tcwv" not in dataset
    assert dataset["prw"].attrs == {
        "standard_name": "atmosphere_mass_content_of_water_vapor",
        "long_name": "Water Vapor Path",
        "units": "kg m-2",
        "cell_methods": "area: time: mean",
        "grid_mapping": "crs",
    }
    crs_attrs = dataset["crs"].attrs
    assert "standard_name" not in crs_attrs
    assert "wkt" not in crs_attrs
    assert crs_attrs["grid_mapping_name"] == "latitude_longitude"
    np.testing.assert_allclose(dataset["prw"], original * 1e-3, rtol=1e-6)
    assert (dataset["lat"].diff("lat") > 0).all()
