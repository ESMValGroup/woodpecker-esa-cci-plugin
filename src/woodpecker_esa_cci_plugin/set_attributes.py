"""Set attributes on ESA CCI variables."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Annotated, Any

import numpy as np
from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from ._options import ConfigurableFix, Options

if TYPE_CHECKING:
    import xarray as xr


def _equal(current: Any, value: Any) -> bool:  # noqa: ANN401
    """Return whether attribute values are equal, including arrays and NaN."""
    if current is None or value is None:
        return current is value
    try:
        return bool(np.array_equal(current, value, equal_nan=True))
    except TypeError:
        # NaN checks are not supported for strings.
        return bool(np.array_equal(current, value))


class SetAttributesOptions(Options):
    """Options of :class:`SetAttributes`."""

    attributes: (
        Annotated[
            dict[str, Annotated[dict[str, Any], Field(min_length=1)]],
            Field(min_length=1),
        ]
        | None
    ) = None


@register_fix_function
class SetAttributes(ConfigurableFix[SetAttributesOptions]):
    """Set attributes on variables where they are missing or wrong.

    The correct attributes are configured with the ``attributes`` option,
    a mapping from variable name to a mapping of attribute names to values.
    Attributes with the value ``None`` are removed. Variables that do not
    exist raise an error.
    """

    suffix = "set_attributes"
    name = "Set attributes"
    description = (
        "Sets attributes on the configured variables when they are missing "
        "or differ from the configured values, and removes attributes "
        "configured as None."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = SetAttributesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, dict[str, object]]:
        wrong = {}
        for var, attrs in (self.options.attributes or {}).items():
            if var not in dataset.variables:
                msg = f"Unable to set attributes on {var}: it does not exist"
                raise ValueError(msg)
            current = dataset[var].attrs
            if changes := {
                key: value
                for key, value in attrs.items()
                if not _equal(current.get(key), value)
            }:
                wrong[var] = changes
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{var} has {key} {dataset[var].attrs.get(key)!r}, "
            + ("expected no value" if value is None else f"expected {value!r}")
            for var, changes in self._wrong(dataset).items()
            for key, value in changes.items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for var, changes in wrong.items():
                attrs = dataset[var].attrs
                for key, value in changes.items():
                    if value is None:
                        del attrs[key]
                    else:
                        # Copy, so datasets do not share lists or dicts with
                        # the recipe options.
                        attrs[key] = copy.deepcopy(value)
        return bool(wrong)
