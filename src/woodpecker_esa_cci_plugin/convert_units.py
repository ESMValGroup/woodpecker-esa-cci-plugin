"""Convert ESA CCI variables to CF units."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import FixFunction, register_fix_function

from .remove_attributes import remove_range_attributes

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# Attributes that name variables with the same units as the variable.
BOUNDS_ATTRIBUTES = ("bounds", "climatology")
# Encoding keys that store the values in the original units.
PACKING_ENCODING = (
    "_FillValue",
    "_Unsigned",
    "add_offset",
    "dtype",
    "missing_value",
    "scale_factor",
)


def _units() -> Any:  # noqa: ANN401
    """Return the CF units registry."""
    # Imported here, because setting up the registry is slow and woodpecker
    # imports this plugin every time it starts.
    from cf_xarray.units import units  # noqa: PLC0415

    return units


def _convert(value: Any, current: str, unit: str) -> Any:  # noqa: ANN401
    """Convert ``value`` from ``current`` to ``unit`` units."""
    return _units().Quantity(value, current).to(unit).magnitude


def _convert_variable(
    variable: xr.Variable,
    current: str,
    unit: str,
) -> xr.Variable:
    """Return ``variable`` with its data converted."""
    # Dimension coordinates cannot be changed in place, so make a copy.
    variable = variable.copy(data=_convert(variable.data, current, unit))
    # The range attributes are in the original units.
    remove_range_attributes(variable)
    encoding = variable.encoding
    packed = "scale_factor" in encoding or "add_offset" in encoding
    # Packed or integer values cannot store the converted values, so let
    # xarray choose a new encoding.
    integer = np.issubdtype(encoding.get("dtype", float), np.integer)
    if packed or integer:
        for key in PACKING_ENCODING:
            encoding.pop(key, None)
    return variable


def _set_units(dataset: xr.Dataset, var: str, unit: str) -> None:
    """Convert ``var`` and its bounds in ``dataset`` to ``unit`` in place."""
    current = dataset[var].attrs["units"]
    convert = _units().Unit(current) != _units().Unit(unit)
    names: list[Hashable] = [var]
    for key in BOUNDS_ATTRIBUTES:
        name = dataset[var].attrs.get(key)
        if name in dataset:
            names.append(name)
    for name in names:
        variable = dataset[name].variable
        if convert:
            variable = _convert_variable(variable, current, unit)
        if name == var or "units" in variable.attrs:
            variable.attrs["units"] = unit
        # Assign to also update the index of dimension coordinates.
        dataset[name] = variable


@register_fix_function
class ConvertUnits(FixFunction):
    """Convert variables to the configured units.

    The units are configured with the ``units`` option, a mapping from
    variable name to units. The units attribute is set to the configured
    string, so it should be a valid CF units string, e.g. ``kg m-2``.
    Bounds variables are converted along with the data. The range
    attributes ``actual_range``, ``valid_min``, ``valid_max`` and
    ``valid_range`` are removed from the converted variables, and so is
    packing encoding that cannot store the converted values. Variables that
    do not exist or have no units attribute raise an error, because they
    cannot be converted.
    """

    suffix = "convert_units"
    name = "Convert units"
    description = (
        "Converts the configured variables to the configured units and sets "
        "their units attribute to the configured string."
    )
    categories = ["metadata", "units"]  # noqa: RUF012
    priority = 40
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VALUE_TRANSFORMATION]  # noqa: RUF012

    def _units(self) -> dict[str, str]:
        raw = self.config.get("units")
        if raw is None:
            return {}
        if not isinstance(raw, Mapping) or not all(
            isinstance(unit, str) for unit in raw.values()
        ):
            msg = (
                "The units option must be a mapping from variable name to "
                "a units string"
            )
            raise TypeError(msg)
        if not raw:
            msg = "The units option must not be empty"
            raise ValueError(msg)
        return {str(var): unit for var, unit in raw.items()}

    def _wrong(self, dataset: xr.Dataset) -> dict[str, str]:
        wrong = {}
        for var, unit in self._units().items():
            if var not in dataset.variables:
                msg = f"Unable to convert {var} to {unit}: it does not exist"
                raise ValueError(msg)
            if "units" not in dataset[var].attrs:
                msg = f"Unable to convert {var} to {unit}: it has no units"
                raise ValueError(msg)
            if dataset[var].attrs["units"] != unit:
                wrong[var] = unit
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{var} has units {dataset[var].attrs['units']!r}, "
            f"expected {unit!r}"
            for var, unit in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for var, unit in wrong.items():
                _set_units(dataset, var, unit)
        return bool(wrong)
