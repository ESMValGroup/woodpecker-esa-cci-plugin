import woodpecker
import xarray as xr

RECIPE_ID = "esa_cci.water_vapour"


def test_recipe_is_discovered_from_package() -> None:
    recipe = woodpecker.recipe.get(RECIPE_ID)

    assert recipe.id == RECIPE_ID


def test_recipe_fixes_dataset(tcwv_dataset: xr.Dataset) -> None:
    recipe = woodpecker.recipe.get(RECIPE_ID)
    dataset = tcwv_dataset.isel(lat=slice(None, None, -1))
    del dataset["tcwv"].attrs["standard_name"]

    findings = woodpecker.recipe.check(dataset, recipe)
    assert set(findings.fix_ids) == {
        "esa_cci.add_tcwv_standard_name",
        "woodpecker.ensure_latitude_is_increasing",
    }

    woodpecker.recipe.apply(dataset, recipe, dry_run=False)

    assert "standard_name" in dataset["tcwv"].attrs
    assert (dataset["lat"].diff("lat") > 0).all()
    assert not woodpecker.recipe.check(dataset, recipe)
