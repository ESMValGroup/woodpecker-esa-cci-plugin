"""Remove attributes from all ESA CCI variables."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import FixFunction, register_fix_function

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
class RemoveAttributes(FixFunction):
    """Remove attributes from all variables.

    The attributes are configured with the ``attributes`` option, a list of
    attribute names. They are removed from all data variables and
    coordinates that have them. Use this for attributes that are hard to
    keep correct, such as the range attributes ``actual_range``,
    ``valid_min``, ``valid_max`` and ``valid_range``: xarray does not use
    them, and they become invalid as soon as the values change.

    xarray stores ``_FillValue`` and ``missing_value`` in the encoding when
    it decodes a dataset, so use ``esa_cci.remove_encoding`` for those.
    """

    suffix = "remove_attributes"
    name = "Remove attributes"
    description = "Removes the configured attributes from all variables."
    categories = ["metadata"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012

    def _attributes(self) -> list[str]:
        raw = self.config.get("attributes")
        if raw is None:
            return []
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
            msg = "The attributes option must be a sequence of attribute names"
            raise TypeError(msg)
        if not raw:
            msg = "The attributes option must not be empty"
            raise ValueError(msg)
        return [str(key) for key in raw]

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[str]]:
        attributes = self._attributes()
        wrong = {}
        for name, variable in dataset.variables.items():
            if keys := [key for key in attributes if key in variable.attrs]:
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
