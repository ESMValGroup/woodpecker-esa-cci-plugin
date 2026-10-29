import importlib
import json
from fnmatch import fnmatch
from types import ModuleType
from typing import get_args

import pytest
import woodpecker
from woodpecker.recipes.models import Recipe

from .esa_cci_data import BUCKET, CASES, STORAGE_OPTIONS, Case, Store

s3fs = pytest.importorskip("s3fs")
# The other stores can only be listed with xcube-cci.
xcube_store: ModuleType | None
try:
    xcube_store = importlib.import_module("xcube.core.store")
except ImportError:
    xcube_store = None

# The recipes of this plugin.
RECIPES = [
    recipe
    for recipe in woodpecker.recipe.list_recipes()
    if recipe.id.startswith("esa_cci.")
]
STORES = get_args(Store)


def _matches(recipe: Recipe, data_id: str) -> bool:
    assert recipe.match is not None
    patterns = recipe.match.path_patterns
    assert patterns
    return any(fnmatch(data_id, pattern) for pattern in patterns)


def _checks(case: Case, recipe: Recipe) -> bool:
    """Return whether ``case`` checks ``recipe``.

    Datasets that provide several variables match a recipe for each, and
    their cases select one of them.
    """
    return _matches(recipe, case.data_id) and case.recipe_id in (
        None,
        recipe.id,
    )


@pytest.fixture(scope="module")
def data_ids() -> dict[Store, list[str]]:
    """Return the data ids of each store that can be listed."""
    fs = s3fs.S3FileSystem(**STORAGE_OPTIONS)
    data_ids: dict[Store, list[str]] = {
        "ccizarr": json.loads(fs.cat(f"{BUCKET}/data_ids.json")),
    }
    if xcube_store is not None:
        for store in ("ccikc", "cciodp"):
            data_store = xcube_store.new_data_store(store)
            data_ids[store] = list(data_store.get_data_ids())
    return data_ids


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_has_cases(recipe: Recipe) -> None:
    assert [case for case in CASES if _checks(case, recipe)]


@pytest.mark.parametrize("store", STORES)
@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_all_datasets_are_checked(
    recipe: Recipe,
    store: Store,
    data_ids: dict[Store, list[str]],
) -> None:
    """Check that the cases are exactly the datasets the recipe matches.

    The datasets come from the ESA CCI Open Data Portal, so this test fails
    when a dataset that the recipe matches is added there without a case, or
    when the dataset of a case is no longer there. Only the zarr store can
    be listed without xcube-cci.
    """
    if store not in data_ids:
        pytest.skip(f"Listing the {store} store needs xcube-cci")
    expected = sorted(i for i in data_ids[store] if _matches(recipe, i))
    checked = sorted(
        case.data_id
        for case in CASES
        if case.store == store and _checks(case, recipe)
    )
    assert checked == expected
