"""Remove attributes from ESA CCI variables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import (
    ConfigurableFix,
    NonEmptyNames,
    Options,
)

if TYPE_CHECKING:
    import xarray as xr


class RemoveAttributesOptions(Options):
    """Options of :class:`RemoveAttributes`."""

    attributes: (
        Annotated[dict[str, NonEmptyNames], Field(min_length=1)] | None
    ) = None


@register_fix_function
class RemoveAttributes(ConfigurableFix[RemoveAttributesOptions]):
    """Remove attributes from variables.

    The attributes are configured with the ``attributes`` option, a mapping
    from variable name to a list of attribute names. Attributes that do not
    exist are ignored, but variables that do not exist raise an error. Use
    ``esa_cci.remove_global_attributes`` to remove global attributes.
    """

    suffix = "remove_attributes"
    name = "Remove attributes"
    description = (
        "Removes the attributes configured with the attributes option, a "
        "mapping from variable name to a list of attribute names."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = RemoveAttributesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, list[str]]:
        wrong = {}
        for var, keys in (self.options.attributes or {}).items():
            if var not in dataset.variables:
                msg = (
                    f"Unable to remove attributes from {var}: it does not "
                    "exist"
                )
                raise ValueError(msg)
            attrs = dataset[var].attrs
            if found := [key for key in keys if key in attrs]:
                wrong[var] = found
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{var} has attributes {', '.join(keys)}"
            for var, keys in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for var, keys in wrong.items():
                attrs = dataset[var].attrs
                for key in keys:
                    del attrs[key]
        return bool(wrong)
