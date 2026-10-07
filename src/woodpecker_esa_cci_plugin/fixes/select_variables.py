"""Select variables from ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import (
    ConfigurableFix,
    NonEmptyNames,
    Options,
)

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterator

    import xarray as xr

# CF attributes that contain a space separated list of variable names.
LIST_ATTRIBUTES = (
    "ancillary_variables",
    "bounds",
    "climatology",
    "coordinates",
    "geometry",
    "interior_ring",
    "node_coordinates",
    "node_count",
    "part_node_count",
)
# CF attributes that contain a list of "key: variable" pairs.
KEY_VALUE_ATTRIBUTES = ("cell_measures", "formula_terms", "grid_mapping")


def _referenced_names(variable: xr.DataArray) -> Iterator[str]:
    """Yield the names of the variables that ``variable`` refers to."""
    for attribute in LIST_ATTRIBUTES:
        yield from str(variable.attrs.get(attribute, "")).split()
    for attribute in KEY_VALUE_ATTRIBUTES:
        words = str(variable.attrs.get(attribute, "")).split()
        if len(words) == 1:
            # grid_mapping may be a single variable name.
            yield words[0]
        else:
            yield from (word for word in words if not word.endswith(":"))


def _required_names(
    dataset: xr.Dataset,
    names: list[str],
) -> set[Hashable]:
    """Return ``names`` and every variable they refer to, recursively."""
    required: set[Hashable] = set()
    todo: list[Hashable] = list(names)
    while todo:
        name = todo.pop()
        if name in required:
            continue
        required.add(name)
        variable = dataset[name]
        todo.extend(variable.coords)
        todo.extend(
            ref for ref in _referenced_names(variable) if ref in dataset
        )
    return required


class SelectVariablesOptions(Options):
    """Options of :class:`SelectVariables`."""

    variables: NonEmptyNames | None = None


@register_fix_function
class SelectVariables(ConfigurableFix[SelectVariablesOptions]):
    """Keep the configured variables and the variables they refer to.

    The variables are configured with the ``variables`` option, a list of
    variable names. Variables they refer to through CF attributes, such as
    ancillary variables and coordinate bounds, are kept as well. Variables
    that do not exist raise an error.
    """

    suffix = "select_variables"
    name = "Select variables"
    description = (
        "Drops all data variables except the ones configured with the "
        "variables option and the variables they refer to through CF "
        "attributes, such as ancillary variables and coordinate bounds."
    )
    categories = ["structure"]  # noqa: RUF012
    # Run after fixes that add references to variables, such as
    # set_attributes adding a grid_mapping.
    priority = 60
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VARIABLE_REMOVAL]  # noqa: RUF012
    options_model = SelectVariablesOptions

    def _unwanted(self, dataset: xr.Dataset) -> list[Hashable]:
        variables = self.options.variables or []
        if not variables:
            return []
        if missing := [name for name in variables if name not in dataset]:
            msg = f"Unable to select {', '.join(missing)}: not in the dataset"
            raise ValueError(msg)
        required = _required_names(dataset, variables)
        return [name for name in dataset.data_vars if name not in required]

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._unwanted(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [f"{name} is not selected" for name in self._unwanted(dataset)]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        unwanted = self._unwanted(dataset)
        if not dry_run:
            for name in unwanted:
                del dataset[name]
        return bool(unwanted)
