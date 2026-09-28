"""Select variables from ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import FixFunction, register_fix_function

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterator

    import xarray as xr

# CF attributes that contain a space separated list of variable names.
LIST_ATTRIBUTES = ("ancillary_variables", "bounds", "coordinates")
# CF attributes that contain a list of "key: variable" pairs.
KEY_VALUE_ATTRIBUTES = ("cell_measures", "grid_mapping")


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
    todo: list[Hashable] = [name for name in names if name in dataset]
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


@register_fix_function
class SelectVariables(FixFunction):
    """Keep the configured variables and the variables they refer to.

    The variables are configured with the ``variables`` option, a list of
    variable names. Variables they refer to through CF attributes, such as
    ancillary variables and coordinate bounds, are kept as well.
    """

    suffix = "select_variables"
    name = "Select variables"
    description = (
        "Drops all data variables except the configured ones and the "
        "variables they refer to."
    )
    categories = ["structure"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VARIABLE_REMOVAL]  # noqa: RUF012

    def _variables(self) -> list[str]:
        raw = self.config.get("variables", [])
        if isinstance(raw, str) or not isinstance(raw, list):
            msg = "The variables option must be a list of variable names"
            raise TypeError(msg)
        return [str(name) for name in raw]

    def _unwanted(self, dataset: xr.Dataset) -> list[Hashable]:
        required = _required_names(dataset, self._variables())
        if not required:
            # Keep everything if none of the variables are present.
            return []
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
