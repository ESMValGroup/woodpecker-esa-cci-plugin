"""Set the global attributes of ESA CCI datasets."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from ._options import ConfigurableFix, Options
from .set_attributes import _equal

if TYPE_CHECKING:
    import xarray as xr


class SetGlobalAttributesOptions(Options):
    """Options of :class:`SetGlobalAttributes`."""

    rename: Annotated[dict[str, str], Field(min_length=1)] | None = None
    attributes: Annotated[dict[str, Any], Field(min_length=1)] | None = None


@register_fix_function
class SetGlobalAttributes(ConfigurableFix[SetGlobalAttributesOptions]):
    """Rename, set and remove global attributes.

    Attributes are renamed with the ``rename`` option, a mapping from the
    current to the new name, which keeps their values, e.g. to replace
    hyphens that CF does not allow in attribute names. The ``attributes``
    option, a mapping from attribute name to value, sets the attributes
    where they are missing or wrong after renaming. Attributes with the
    value ``None`` are removed. Renaming an attribute that does not exist,
    or to a name that already exists, raises an error.
    """

    suffix = "set_global_attributes"
    name = "Set global attributes"
    description = (
        "Renames the configured global attributes, then sets them when they "
        "are missing or differ from the configured values, and removes "
        "attributes configured as None."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = SetGlobalAttributesOptions

    def _rename(self, dataset: xr.Dataset) -> dict[str, str]:
        wrong = {}
        for old, new in (self.options.rename or {}).items():
            if old in dataset.attrs and new not in dataset.attrs:
                wrong[old] = new
            elif old in dataset.attrs:
                msg = f"Unable to rename {old} to {new}: {new} already exists"
                raise ValueError(msg)
            elif new not in dataset.attrs:
                msg = f"Unable to rename {old} to {new}: {old} does not exist"
                raise ValueError(msg)
        return wrong

    def _wrong(
        self, dataset: xr.Dataset
    ) -> tuple[dict[str, str], dict[str, object]]:
        """Return the attributes to rename, and to set afterwards."""
        rename = self._rename(dataset)
        attrs = {rename.get(key, key): v for key, v in dataset.attrs.items()}
        changes = {
            key: value
            for key, value in (self.options.attributes or {}).items()
            if not _equal(attrs.get(key), value)
        }
        return rename, changes

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return any(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        rename, changes = self._wrong(dataset)
        return [
            f"global attribute {old} should be named {new}"
            for old, new in rename.items()
        ] + [
            f"global attribute {key} is {dataset.attrs.get(key)!r}, "
            + ("expected no value" if value is None else f"expected {value!r}")
            for key, value in changes.items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        rename, changes = self._wrong(dataset)
        if not dry_run:
            attrs = dataset.attrs
            for old, new in rename.items():
                attrs[new] = attrs.pop(old)
            for key, value in changes.items():
                if value is None:
                    del attrs[key]
                else:
                    # Copy, so datasets do not share lists or dicts with the
                    # recipe options.
                    attrs[key] = copy.deepcopy(value)
        return bool(rename or changes)
