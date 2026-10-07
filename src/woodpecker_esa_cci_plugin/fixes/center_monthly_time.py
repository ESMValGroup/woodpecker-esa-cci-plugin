"""Center ESA CCI monthly time points in whole calendar months."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np
import xarray as xr
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .set_time_units import _is_decoded

if TYPE_CHECKING:
    from numpy.typing import NDArray

# The name of the dimension of the two bounds of each cell, for bounds that
# are added.
BOUNDS_DIMENSION = "bnds"


def _decoded(
    dataset: xr.Dataset, name: str, coordinate: str | None = None
) -> xr.Variable:
    """Return variable ``name`` of ``dataset`` with decoded times.

    Bounds inherit the units and calendar of their ``coordinate``.
    """
    variable = dataset[name].variable
    if _is_decoded(variable):
        return variable
    inherited = {}
    if coordinate is not None:
        attrs = dataset[coordinate].attrs
        inherited = {
            key: attrs[key] for key in ("units", "calendar") if key in attrs
        }
    variable = variable.copy(deep=False)
    variable.attrs = {**inherited, **variable.attrs}
    return xr.conventions.decode_cf_variable(name, variable)


def _encoded(
    original: xr.Variable,
    decoded: xr.Variable,
    values: NDArray[np.datetime64],
    name: str,
) -> xr.Variable:
    """Return ``values`` encoded like ``original``."""
    variable = decoded.copy(data=values)
    # The times are not whole days or seconds anymore.
    variable.encoding["dtype"] = np.dtype("float64")
    if _is_decoded(original):
        return variable
    # Keep times without fill value, xarray otherwise adds one to floating
    # point times.
    variable.encoding.setdefault("_FillValue", None)
    return xr.conventions.encode_cf_variable(variable, name=name)


def _months(
    name: str, times: NDArray[np.datetime64]
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """Return the middle and bounds of the calendar months of ``times``."""
    if not np.issubdtype(times.dtype, np.datetime64):
        msg = (
            f"Unable to center {name} in calendar months: it is not decoded "
            "to numpy datetime64"
        )
        raise ValueError(msg)
    start = times.astype("datetime64[M]")
    end = start + np.timedelta64(1, "M")
    bounds = np.stack([start, end], axis=1).astype(times.dtype)
    middle = bounds[:, 0] + (bounds[:, 1] - bounds[:, 0]) / 2
    return cast("NDArray[np.datetime64]", middle), bounds


class CenterMonthlyTimeOptions(Options):
    """Options of :class:`CenterMonthlyTime`."""

    coordinate: str | None = None


@register_fix_function
class CenterMonthlyTime(ConfigurableFix[CenterMonthlyTimeOptions]):
    """Center monthly time points in the calendar months they are in.

    The monthly time coordinate is configured with the ``coordinate`` option.
    Its bounds are set to the start of the calendar month of each time point
    and the start of the next month, and the time points to the middle of
    their bounds, as CMIP7 requires for monthly means. Coordinates without
    bounds get a bounds variable named after the coordinate with a ``_bnds``
    suffix. A coordinate that does not exist, is not a dimension coordinate
    or has two time points in the same month raises an error.
    """

    suffix = "center_monthly_time"
    name = "Center monthly time"
    description = (
        "Sets the bounds of the monthly time coordinate configured with the "
        "coordinate option to whole calendar months, and the time points to "
        "the middle of their month, as CMIP7 requires for monthly means."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = CenterMonthlyTimeOptions

    def _wrong(
        self, dataset: xr.Dataset
    ) -> tuple[str, NDArray[np.datetime64], NDArray[np.datetime64]] | None:
        """Return the coordinate, and its correct values and bounds."""
        name = self.options.coordinate
        if name is None:
            return None
        if name not in dataset.variables:
            msg = (
                f"Unable to center {name} in calendar months: it does not "
                "exist"
            )
            raise ValueError(msg)
        if dataset[name].dims != (name,):
            msg = (
                f"Unable to center {name} in calendar months: it is not a "
                "dimension coordinate"
            )
            raise ValueError(msg)
        times = _decoded(dataset, name).to_numpy()
        middle, bounds = _months(name, times)
        if np.unique(bounds[:, 0]).size != bounds.shape[0]:
            msg = (
                f"Unable to center {name} in calendar months: it has several "
                "time points in the same month"
            )
            raise ValueError(msg)
        current_bounds = None
        bounds_name = dataset[name].attrs.get("bounds")
        if isinstance(bounds_name, str) and bounds_name in dataset.variables:
            current_bounds = _decoded(dataset, bounds_name, name).to_numpy()
        if (
            current_bounds is None
            or not np.array_equal(times, middle)
            or not np.array_equal(current_bounds, bounds)
        ):
            return name, middle, bounds
        return None

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._wrong(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (found := self._wrong(dataset)) is None:
            return []
        name = found[0]
        return [
            (
                f"{name} is not centered in calendar months, or its bounds "
                "are not whole calendar months"
            )
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
            name, middle, bounds = found
            variable = dataset[name].variable
            decoded = _decoded(dataset, name)
            bounds_name = variable.attrs.get("bounds")
            if (
                isinstance(bounds_name, str)
                and bounds_name in dataset.variables
            ):
                original = dataset[bounds_name].variable
                decoded_bounds = _decoded(dataset, bounds_name, name)
            else:
                bounds_name = f"{name}_bnds"
                original = variable
                decoded_bounds = xr.Variable(
                    (name, BOUNDS_DIMENSION),
                    bounds,
                    encoding=dict(decoded.encoding),
                )
            dataset[bounds_name] = _encoded(
                original, decoded_bounds, bounds, bounds_name
            )
            # Assign to also update the index.
            dataset[name] = _encoded(variable, decoded, middle, name)
            dataset[name].attrs["bounds"] = bounds_name
        return True
