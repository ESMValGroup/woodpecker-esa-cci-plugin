"""Set the units that ESA CCI time coordinates are stored in."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import numpy as np
from pydantic import model_validator
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    import xarray as xr


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
    """Set the units and calendar that a decoded time coordinate is stored in.

    The time coordinate is configured with the ``coordinate`` option, the
    units with the ``units`` option, e.g. ``days since 1850-01-01``, and the
    calendar with the ``calendar`` option, e.g. ``standard``. At least one
    of ``units`` and ``calendar`` must be set. Xarray keeps the units and
    calendar in the encoding of decoded times, so this changes how the times
    are written, not their values. The coordinate bounds get the same units
    and calendar. When the units change, integer storage is replaced by
    float64, because times may not be whole numbers of the new units. A
    coordinate that does not exist or is not decoded to dates raises an
    error.
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
        if not np.issubdtype(dataset[name].dtype, np.datetime64):
            msg = f"Unable to set the units of {name}: it is not decoded"
            raise ValueError(msg)
        encoding = dataset[name].encoding
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
        encoding = dataset[name].encoding
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
            for var in names:
                encoding = dataset[var].encoding
                encoding.update(changes)
                if "units" in changes:
                    encoding["dtype"] = np.dtype("float64")
        return True
