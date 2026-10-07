"""Remove global attributes from ESA CCI datasets."""

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
    import xarray as xr


class RemoveGlobalAttributesOptions(Options):
    """Options of :class:`RemoveGlobalAttributes`."""

    attributes: NonEmptyNames | None = None


@register_fix_function
class RemoveGlobalAttributes(ConfigurableFix[RemoveGlobalAttributesOptions]):
    """Remove global attributes.

    The attributes are configured with the ``attributes`` option, a list of
    attribute names. Attributes that do not exist are ignored.
    """

    suffix = "remove_global_attributes"
    name = "Remove global attributes"
    description = (
        "Removes the global attributes configured with the attributes option, "
        "a list of attribute names."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = RemoveGlobalAttributesOptions

    def _wrong(self, dataset: xr.Dataset) -> list[str]:
        return [
            key
            for key in self.options.attributes or []
            if key in dataset.attrs
        ]

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"dataset has global attribute {key}"
            for key in self._wrong(dataset)
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for key in wrong:
                del dataset.attrs[key]
        return bool(wrong)
