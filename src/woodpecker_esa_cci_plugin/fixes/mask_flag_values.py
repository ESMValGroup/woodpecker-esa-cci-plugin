"""Mask flag values in ESA CCI variables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Self

import numpy as np
from pydantic import Field, model_validator
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    import xarray as xr

# The attributes that describe the flags.
FLAG_ATTRIBUTES = ("flag_values", "flag_meanings")


class ValidRange(Options):
    """The range of the data values of a variable with flags."""

    valid_min: float | None = None
    valid_max: float | None = None

    @model_validator(mode="after")
    def _min_or_max(self) -> Self:
        if self.valid_min is None and self.valid_max is None:
            msg = "Set valid_min, valid_max or both"
            raise ValueError(msg)
        return self


class MaskFlagValuesOptions(Options):
    """Options of :class:`MaskFlagValues`."""

    variables: Annotated[dict[str, ValidRange], Field(min_length=1)] | None = (
        None
    )


@register_fix_function
class MaskFlagValues(ConfigurableFix[MaskFlagValuesOptions]):
    """Replace the flags in the data of variables by missing values.

    The variables are configured with the ``variables`` option, a mapping
    from variable name to the ``valid_min`` and ``valid_max`` of its data
    values. Values outside that range are flags, and become missing values.
    The ``flag_values`` and ``flag_meanings`` attributes are removed, so a
    variable with a ``flag_values`` attribute has flags in its data.
    Variables that do not exist raise an error.
    """

    suffix = "mask_flag_values"
    name = "Mask flag values"
    description = (
        "Replaces the flags in the data of the variables configured with the "
        "variables option, a mapping from variable name to the valid_min and "
        "valid_max of its data values, by missing values, and removes the "
        "flag_values and flag_meanings attributes. Values outside the range "
        "are flags. Some ESA CCI datasets store flags, e.g. for clouds, water "
        "or missing satellite data, in the same variable as the data, where "
        "they would be used as data values. They do not always list all the "
        "flags they use, and the Open Data Portal store can give wrong flag "
        "values, so the flags are found by the range of the data values."
    )
    categories = ["data"]  # noqa: RUF012
    # Before fixes that change the values, such as unit conversions.
    priority = 35
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VALUE_TRANSFORMATION]  # noqa: RUF012
    options_model = MaskFlagValuesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, ValidRange]:
        wrong = {}
        for var, valid in (self.options.variables or {}).items():
            if var not in dataset.variables:
                msg = f"Unable to mask flags in {var}: it does not exist"
                raise ValueError(msg)
            if "flag_values" in dataset[var].attrs:
                wrong[var] = valid
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [f"{var} has flags in its data" for var in self._wrong(dataset)]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for var, valid in wrong.items():
                _mask(dataset, var, valid)
        return bool(wrong)


def _mask(dataset: xr.Dataset, var: str, valid: ValidRange) -> None:
    """Mask the values outside ``valid`` in ``var`` of ``dataset``."""
    variable = dataset[var].variable
    data = variable.data
    # Comparisons with the data, so the mask is lazy for lazy data.
    lowest = -np.inf if valid.valid_min is None else valid.valid_min
    highest = np.inf if valid.valid_max is None else valid.valid_max
    flags = (data < lowest) | (data > highest)
    # Integer data cannot have missing values.
    data = data.astype(np.result_type(data.dtype, np.float32))
    variable = variable.copy(data=np.where(flags, np.nan, data))
    for key in FLAG_ATTRIBUTES:
        variable.attrs.pop(key, None)
    dataset[var] = variable
