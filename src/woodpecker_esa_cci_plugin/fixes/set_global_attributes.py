"""Set the global attributes of ESA CCI datasets."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .set_attributes import Attributes, _equal

if TYPE_CHECKING:
    import xarray as xr


class SetGlobalAttributesOptions(Options):
    """Options of :class:`SetGlobalAttributes`."""

    attributes: Attributes | None = None


@register_fix_function
class SetGlobalAttributes(ConfigurableFix[SetGlobalAttributesOptions]):
    """Set global attributes where they are missing or wrong.

    The correct attributes are configured with the ``attributes`` option, a
    mapping from attribute name to value. Use
    ``esa_cci.remove_global_attributes`` to remove global attributes.
    """

    suffix = "set_global_attributes"
    name = "Set global attributes"
    description = (
        "Sets the global attributes configured with the attributes option, a "
        "mapping from attribute name to value, when they are missing or "
        "differ from the configured values."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = SetGlobalAttributesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, object]:
        return {
            key: value
            for key, value in (self.options.attributes or {}).items()
            if not _equal(dataset.attrs.get(key), value)
        }

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"global attribute {key} is {dataset.attrs.get(key)!r}, "
            f"expected {value!r}"
            for key, value in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        changes = self._wrong(dataset)
        if not dry_run:
            for key, value in changes.items():
                # Copy, so datasets do not share lists or dicts with the
                # recipe options.
                dataset.attrs[key] = copy.deepcopy(value)
        return bool(changes)
