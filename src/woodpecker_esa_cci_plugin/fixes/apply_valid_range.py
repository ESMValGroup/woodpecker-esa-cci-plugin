"""Mask the values outside the valid range of ESA CCI variables."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import (
    ConfigurableFix,
    NonEmptyNames,
    Options,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import xarray as xr

# The CF attributes that describe the valid range of the values.
VALID_RANGE_ATTRIBUTES = ("valid_range", "valid_min", "valid_max")
# Encoding keys of packed data, whose valid range CF defines in the packed
# values.
PACKING_ENCODING = ("scale_factor", "add_offset")


def _valid_range(attrs: Mapping[object, object]) -> tuple[float, float]:
    """Return the lowest and highest valid value from ``attrs``."""
    lowest, highest = -np.inf, np.inf
    if "valid_range" in attrs:
        lowest, highest = np.asarray(attrs["valid_range"], dtype=float)
    lowest = float(np.asarray(attrs.get("valid_min", lowest)))
    highest = float(np.asarray(attrs.get("valid_max", highest)))
    return lowest, highest


class ApplyValidRangeOptions(Options):
    """Options of :class:`ApplyValidRange`."""

    variables: NonEmptyNames | None = None


@register_fix_function
class ApplyValidRange(ConfigurableFix[ApplyValidRangeOptions]):
    """Replace the values outside the valid range by missing values.

    The variables are configured with the ``variables`` option, a list of
    variable names. Their values outside the range of their ``valid_range``,
    ``valid_min`` and ``valid_max`` attributes become missing values, and
    those attributes are removed, so a variable with one of them has not
    been masked yet. Variables that do not exist or are packed raise an
    error, because CF defines the valid range of packed variables in the
    packed values.
    """

    suffix = "apply_valid_range"
    name = "Apply valid range"
    description = (
        "Replaces the values of the variables configured with the variables "
        "option that are outside the range of their valid_range, valid_min "
        "and valid_max attributes by missing values, and removes these "
        "attributes. CF defines values outside the valid range as missing "
        "values, but xarray does not mask them. Some ESA CCI datasets "
        "store missing values as a number outside the valid range, e.g. "
        "-9.9, without a fill value."
    )
    categories = ["data"]  # noqa: RUF012
    # Before esa_cci.remove_range_attributes and fixes that change the
    # values, such as unit conversions.
    priority = 25
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VALUE_TRANSFORMATION]  # noqa: RUF012
    options_model = ApplyValidRangeOptions

    def _wrong(self, dataset: xr.Dataset) -> list[str]:
        wrong = []
        for var in self.options.variables or []:
            if var not in dataset.variables:
                msg = (
                    f"Unable to apply the valid range of {var}: it does not "
                    "exist"
                )
                raise ValueError(msg)
            variable = dataset[var].variable
            if not any(
                key in variable.attrs for key in VALID_RANGE_ATTRIBUTES
            ):
                continue
            if any(key in variable.encoding for key in PACKING_ENCODING):
                msg = f"Unable to apply the valid range of {var}: it is packed"
                raise ValueError(msg)
            wrong.append(var)
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{var} may have values outside its valid range"
            for var in self._wrong(dataset)
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for var in wrong:
                _mask(dataset, var)
        return bool(wrong)


def _mask(dataset: xr.Dataset, var: str) -> None:
    """Mask the values outside the valid range of ``var`` in ``dataset``."""
    variable = dataset[var].variable
    lowest, highest = _valid_range(variable.attrs)
    data = variable.data
    # Comparisons with the data, so the mask is lazy for lazy data.
    invalid = (data < lowest) | (data > highest)
    # Integer data cannot have missing values.
    data = data.astype(np.result_type(data.dtype, np.float32))
    variable = variable.copy(data=np.where(invalid, np.nan, data))
    for key in VALID_RANGE_ATTRIBUTES:
        variable.attrs.pop(key, None)
    dataset[var] = variable
