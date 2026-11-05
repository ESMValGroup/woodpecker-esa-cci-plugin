"""Add variables to ESA CCI datasets that are the sum of other variables."""

from __future__ import annotations

import operator
from functools import reduce
from typing import TYPE_CHECKING, Annotated

from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    import xarray as xr


class SumVariablesOptions(Options):
    """Options of :class:`SumVariables`."""

    sums: (
        Annotated[
            dict[str, Annotated[list[str], Field(min_length=2)]],
            Field(min_length=1),
        ]
        | None
    ) = None


@register_fix_function
class SumVariables(ConfigurableFix[SumVariablesOptions]):
    """Replace variables by their sum.

    The sums are configured with the ``sums`` option, a mapping from the name
    of a new variable to the names of the variables to add up. These are
    removed, and the new variable only gets their units as attributes, because
    their other attributes describe the terms and not the sum. It is missing
    where any of the terms is missing, because the sum is unknown there.
    Terms that do not exist, that do not have the same units, or a new
    variable that exists while its terms do too, raise an error.
    """

    suffix = "sum_variables"
    name = "Sum variables"
    description = (
        "Replaces the variables configured with the sums option, a mapping "
        "from the name of a new variable to the names of the variables to "
        "add up, by their sum. Some variables that CMIP7 requests are not in "
        "the ESA CCI datasets, but their components are. The sum is missing "
        "where any of the terms is missing, and only has the units of the "
        "terms as attributes, so set its other attributes with "
        "esa_cci.set_attributes."
    )
    categories = ["data"]  # noqa: RUF012
    # Before the fixes that set the attributes of the sum and convert it.
    priority = 25
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VALUE_TRANSFORMATION]  # noqa: RUF012
    options_model = SumVariablesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, list[str]]:
        wrong = {}
        for name, terms in (self.options.sums or {}).items():
            action = f"Unable to add {name}"
            present = [term for term in terms if term in dataset.variables]
            if name in dataset.variables:
                if present:
                    msg = f"{action}: it already exists"
                    raise ValueError(msg)
                continue
            if missing := sorted(set(terms) - set(present)):
                msg = f"{action}: {', '.join(missing)} do not exist"
                raise ValueError(msg)
            units = {dataset[term].attrs.get("units") for term in terms}
            if len(units) > 1 or None in units:
                msg = f"{action}: its terms do not have the same units"
                raise ValueError(msg)
            wrong[name] = terms
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{name} is missing, the sum of {', '.join(terms)}"
            for name, terms in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name, terms in wrong.items():
                _replace_by_sum(dataset, name, terms)
        return bool(wrong)


def _replace_by_sum(dataset: xr.Dataset, name: str, terms: list[str]) -> None:
    """Replace ``terms`` in ``dataset`` by their sum, called ``name``."""
    total = reduce(operator.add, (dataset[term].variable for term in terms))
    total.attrs = {"units": dataset[terms[0]].attrs["units"]}
    dataset[name] = total
    for term in terms:
        del dataset[term]
