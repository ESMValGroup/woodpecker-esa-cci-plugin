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
from woodpecker_esa_cci_plugin.references import referenced_names

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr


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
            ref for ref in referenced_names(variable.attrs) if ref in dataset
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
    ancillary variables and coordinate bounds, are kept as well, and so are
    their coordinates. Other coordinates, such as those of histogram bins
    that only other variables use, are dropped. Variables that do not exist
    raise an error.
    """

    suffix = "select_variables"
    name = "Select variables"
    description = (
        "Drops all data variables except the ones configured with the "
        "variables option and the variables they refer to through CF "
        "attributes, such as ancillary variables and coordinate bounds, and "
        "the coordinates that none of these variables use."
    )
    categories = ["structure"]  # noqa: RUF012
    # Run after fixes that add references to variables, such as
    # fix_variable_references adding ancillary variables.
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
        return [name for name in dataset.variables if name not in required]

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
