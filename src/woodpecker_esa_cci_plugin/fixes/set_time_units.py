"""Set the units that ESA CCI time coordinates are stored in."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import numpy as np
import xarray as xr
from pydantic import model_validator
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import MutableMapping


def _is_decoded(variable: xr.Variable) -> bool:
    """Return whether ``variable`` contains decoded times."""
    return np.issubdtype(variable.dtype, np.datetime64) or (
        variable.dtype == object
    )


def _time_encoding(variable: xr.Variable) -> MutableMapping[Any, Any]:
    """Return where the units and calendar of ``variable`` are stored.

    xarray moves them from the attributes to the encoding when it decodes
    times.
    """
    return variable.encoding if _is_decoded(variable) else variable.attrs


class SetTimeUnitsOptions(Options):
    """Options of :class:`SetTimeUnits`."""

    coordinate: str | None = None
    units: str | None = None
    calendar: str | None = None

    @model_validator(mode="after")
    def _coordinate_and_encoding(self) -> Self:
        encoding = self.units is not None or self.calendar is not None
        if (self.coordinate is not None) != encoding:
            msg = (
                "The coordinate option and the units or calendar option must "
                "be set"
            )
            raise ValueError(msg)
        return self


@register_fix_function
class SetTimeUnits(ConfigurableFix[SetTimeUnitsOptions]):
    """Set the units and calendar that a time coordinate is stored in.

    The time coordinate is configured with the ``coordinate`` option, the
    units with the ``units`` option, e.g. ``days since 1850-01-01``, and the
    calendar with the ``calendar`` option, e.g. ``standard``. At least one
    of ``units`` and ``calendar`` must be set. Xarray keeps the units and
    calendar in the encoding of decoded times, so for those this changes how
    the times are written, not their values. Times that are not decoded are
    converted to the new units and calendar. The coordinate bounds get the
    same units and calendar. When the units change, integer storage is
    replaced by float64, because times may not be whole numbers of the new
    units. A coordinate that does not exist or does not contain times raises
    an error.
    """

    suffix = "set_time_units"
    name = "Set time units"
    description = (
        "Sets the units and calendar that the configured time coordinate and "
        "its bounds are stored in."
    )
    categories = ["metadata", "units"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = SetTimeUnitsOptions

    def _wrong(self, dataset: xr.Dataset) -> tuple[str, dict[str, str]] | None:
        """Return the coordinate and the encoding that needs to be set."""
        name = self.options.coordinate
        if name is None:
            return None
        wanted = {
            key: value
            for key, value in [
                ("units", self.options.units),
                ("calendar", self.options.calendar),
            ]
            if value is not None
        }
        if name not in dataset.variables:
            msg = f"Unable to set the units of {name}: it does not exist"
            raise ValueError(msg)
        variable = dataset[name].variable
        if not _is_decoded(variable) and " since " not in str(
            variable.attrs.get("units")
        ):
            msg = (
                f"Unable to set the units of {name}: it does not contain times"
            )
            raise ValueError(msg)
        encoding = _time_encoding(variable)
        if changes := {
            key: value
            for key, value in wanted.items()
            if encoding.get(key) != value
        }:
            return name, changes
        return None

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._wrong(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (found := self._wrong(dataset)) is None:
            return []
        name, changes = found
        encoding = _time_encoding(dataset[name].variable)
        return [
            f"{name} is stored with {key} {encoding.get(key)!r}, "
            f"expected {value!r}"
            for key, value in changes.items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (found := self._wrong(dataset)) is None:
            return False
        if not dry_run:
            name, changes = found
            names = [name]
            bounds = dataset[name].attrs.get("bounds")
            if isinstance(bounds, str) and bounds in dataset.variables:
                names.append(bounds)
            # CF allows bounds to inherit the units and calendar of their
            # coordinate.
            inherited = {
                key: dataset[name].attrs[key]
                for key in ("units", "calendar")
                if key in dataset[name].attrs
            }
            for var in names:
                variable = dataset[var].variable
                if _is_decoded(variable):
                    _set_encoding(variable, changes)
                else:
                    # Decode the times, so they are encoded again with the
                    # new units and calendar.
                    variable = variable.copy(deep=False)
                    variable.attrs = {**inherited, **variable.attrs}
                    decoded = xr.conventions.decode_cf_variable(var, variable)
                    _set_encoding(decoded, changes)
                    # Keep times without fill value, xarray otherwise adds
                    # one to floating point times.
                    decoded.encoding.setdefault("_FillValue", None)
                    dataset[var] = xr.conventions.encode_cf_variable(
                        decoded, name=var
                    )
        return True


def _set_encoding(variable: xr.Variable, changes: dict[str, str]) -> None:
    """Set the units and calendar that decoded ``variable`` is stored in."""
    variable.encoding.update(changes)
    if "units" in changes:
        variable.encoding["dtype"] = np.dtype("float64")
