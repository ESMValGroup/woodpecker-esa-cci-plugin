from importlib.resources import files

import numpy as np
import pytest
import woodpecker
import xarray as xr
import yaml
from woodpecker.fixes.registry import FixFunctionRegistry

from woodpecker_esa_cci_plugin.remove_attributes import RANGE_ATTRIBUTES

RECIPE_ID = "esa_cci.water_vapour"
# The ids of all recipes shipped with the plugin.
RECIPE_IDS = sorted(
    recipe["id"]
    for path in (files("woodpecker_esa_cci_plugin") / "recipes").iterdir()
    if path.name.endswith(".yaml")
    for recipe in yaml.safe_load(path.read_text(encoding="utf-8"))["recipes"]
)
PACKING_KEYS = (
    "_FillValue",
    "_Unsigned",
    "add_offset",
    "dtype",
    "missing_value",
    "scale_factor",
)


def test_recipes_are_found() -> None:
    assert RECIPE_ID in RECIPE_IDS


@pytest.mark.parametrize("recipe_id", RECIPE_IDS)
def test_recipe_is_discovered_and_valid(recipe_id: str) -> None:
    # Woodpecker discovers the recipes through the plugin entry point.
    recipe = woodpecker.recipe.get(recipe_id)
    for step in recipe.steps:
        fix_id = recipe.resolve_fix_identifier(step)
        # Fixes of this plugin validate their options when configured.
        FixFunctionRegistry.instantiate(fix_id).configure(step.options)


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
        "esa_cci.remove_attributes",
        "esa_cci.remove_encoding",
        "esa_cci.set_global_attributes",
        "esa_cci.set_time_units",
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
    for name in ("stdv", "num_obs"):
        assert "standard_name" not in tcwv_dataset[name].attrs
    assert tcwv_dataset["time"].attrs["units_metadata"] == "leap_seconds: none"

    # CF does not allow hyphens in attribute names.
    attrs = tcwv_dataset.attrs
    assert attrs["Conventions"] == "CF-1.11"
    assert not [key for key in attrs if "-" in key]
    assert (
        attrs["keywords_vocabulary"] == (original.attrs["keywords-vocabulary"])
    )
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

    # The bounds variables inherit their attributes from the coordinates.
    for name in ("lat_bnds", "lon_bnds", "time_bnds"):
        attrs = tcwv_dataset[name].attrs
        for key in ("standard_name", "long_name", "comment"):
            assert key not in attrs

    # Range attributes and packing are removed, but the time encoding stays.
    for var, variable in tcwv_dataset.variables.items():
        assert not set(RANGE_ATTRIBUTES) & set(variable.attrs)
        if var in ("time", "time_bnds"):
            assert variable.encoding == {
                **original[var].encoding,
                "calendar": "standard",
            }
        else:
            assert not set(PACKING_KEYS) & set(variable.encoding)
