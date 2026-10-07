"""Remove the range attributes from all ESA CCI variables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# Attributes that describe the range of the values of a variable. They become
# invalid when the values change, e.g. in a unit conversion.
RANGE_ATTRIBUTES = ("actual_range", "valid_max", "valid_min", "valid_range")


def remove_range_attributes(variable: xr.Variable) -> None:
    """Remove the attributes that describe the range of ``variable``."""
    for key in RANGE_ATTRIBUTES:
        variable.attrs.pop(key, None)


@register_fix_function
class RemoveRangeAttributes(ConfigurableFix[Options]):
    """Remove the range attributes from all variables.

    The range attributes ``actual_range``, ``valid_min``, ``valid_max`` and
    ``valid_range`` are removed from all data variables and coordinates that
    have them. xarray does not use them, and they become invalid as soon as
    the values change.
    """

    suffix = "remove_range_attributes"
    name = "Remove range attributes"
    description = (
        "Removes the range attributes actual_range, valid_min, valid_max and "
        "valid_range from all variables. xarray does not use them, and they "
        "become invalid as soon as the values change."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = Options

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[str]]:
        wrong = {}
        for name, variable in dataset.variables.items():
            if keys := [
                key for key in RANGE_ATTRIBUTES if key in variable.attrs
            ]:
                wrong[name] = keys
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{name} has attributes {', '.join(keys)}"
            for name, keys in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name, keys in wrong.items():
                attrs = dataset.variables[name].attrs
                for key in keys:
                    del attrs[key]
        return bool(wrong)
