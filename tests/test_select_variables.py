from typing import Any

import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.select_variables"
OPTIONS = {FIX_ID: {"variables": ["tcwv"]}}


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    """Make tcwv refer to its grid mapping, like the recipe does."""
    tcwv_dataset["tcwv"].attrs["grid_mapping"] = "crs"
    return tcwv_dataset


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


@pytest.mark.parametrize(
    ("variables", "match"),
    [([], "must not be empty"), (["tcwv", "prw"], "select prw: not in")],
)
def test_missing_variable_raises(
    dataset: xr.Dataset,
    variables: list[str],
    match: str,
) -> None:
    options = {FIX_ID: {"variables": variables}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_tuple_option_is_accepted(dataset: xr.Dataset) -> None:
    options = {FIX_ID: {"variables": ("tcwv",)}}

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=options)
    assert "tcwv_err" not in dataset


@pytest.mark.parametrize("variables", ["tcwv", b"tcwv"])
def test_invalid_option_raises(
    dataset: xr.Dataset,
    variables: str | bytes,
) -> None:
    options = {FIX_ID: {"variables": variables}}

    with pytest.raises(TypeError, match="variables option"):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)


def test_referenced_variables_are_kept(dataset: xr.Dataset) -> None:
    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    # One finding for each variable that is dropped.
    assert findings.fix_ids == (FIX_ID,) * 4

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    assert "tcwv_err" in dataset

    result = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS
    )
    assert result.changed == 1
    assert set(dataset.data_vars) == {
        "tcwv",
        "stdv",
        "num_obs",
        "crs",
        "lat_bnds",
        "lon_bnds",
        "time_bnds",
    }
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_formula_terms_and_climatology_are_kept(dataset: xr.Dataset) -> None:
    dataset["lev"] = xr.DataArray(
        [0.5],
        dims="lev",
        attrs={"formula_terms": "sigma: lev ps: ps ptop: ptop"},
    )
    dataset["ps"] = dataset["tcwv"].copy()
    dataset["ptop"] = xr.DataArray(0.0)
    dataset["tcwv"] = dataset["tcwv"].expand_dims("lev")
    dataset["time"].attrs["climatology"] = "climatology_bnds"
    dataset["climatology_bnds"] = dataset["time"].expand_dims(nv=2).T

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert {"ps", "ptop", "climatology_bnds"} <= set(dataset.data_vars)
    assert "tcwv_err" not in dataset


def test_runs_after_fixes_that_add_references(dataset: xr.Dataset) -> None:
    del dataset["tcwv"].attrs["grid_mapping"]
    options: dict[str, dict[str, Any]] = {
        **OPTIONS,
        "esa_cci.set_attributes": {
            "attributes": {"tcwv": {"grid_mapping": "crs"}},
        },
    }

    # Without an explicit list of fixes, woodpecker orders them by priority.
    woodpecker.apply(
        dataset,
        dataset="ESA-CCI",
        dry_run=False,
        options=options,
    )
    assert "crs" in dataset


def test_geometry_references_are_kept(dataset: xr.Dataset) -> None:
    dataset["tcwv"].attrs["geometry"] = "geometry_container"
    dataset["geometry_container"] = xr.DataArray(
        0,
        attrs={
            "node_coordinates": "x y",
            "node_count": "node_count",
            "part_node_count": "part_node_count",
            "interior_ring": "interior_ring",
        },
    )
    names = ("x", "y", "node_count", "part_node_count", "interior_ring")
    for name in names:
        dataset[name] = xr.DataArray([0])

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert {"geometry_container", *names} <= set(dataset.data_vars)
