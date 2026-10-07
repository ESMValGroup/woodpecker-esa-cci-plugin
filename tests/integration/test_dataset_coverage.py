import json
from fnmatch import fnmatch

import pytest
import woodpecker
from woodpecker.recipes.models import Recipe

from .esa_cci_data import BUCKET, CASES, STORAGE_OPTIONS

s3fs = pytest.importorskip("s3fs")

# The recipes of this plugin.
RECIPES = [
    recipe
    for recipe in woodpecker.recipe.list_recipes()
    if recipe.id.startswith("esa_cci.")
]


@pytest.fixture(scope="module")
def data_ids() -> list[str]:
    fs = s3fs.S3FileSystem(**STORAGE_OPTIONS)
    data_ids: list[str] = json.loads(fs.cat(f"{BUCKET}/data_ids.json"))
    return data_ids


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_all_datasets_are_checked(
    recipe: Recipe,
    data_ids: list[str],
) -> None:
    """Check that the cases are exactly the datasets the recipe matches.

    The datasets come from the ESA CCI Open Data Portal, so this test fails
    when a dataset that the recipe matches is added there without a case, or
    when the dataset of a case is no longer there.
    """
    assert recipe.match is not None
    patterns = recipe.match.path_patterns
    assert patterns

    def matches(data_id: str) -> bool:
        return any(fnmatch(data_id, pattern) for pattern in patterns)

    expected = sorted(i for i in data_ids if matches(i))
    assert expected
    checked = sorted(case.data_id for case in CASES if matches(case.data_id))
    assert checked == expected
