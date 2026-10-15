"""Center ESA CCI time points in whole calendar months or days."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple, cast

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
# The CMIP frequencies of the time coordinates that the fix centers.
Frequency = Literal["mon", "day"]
# The numpy datetime units of the calendar periods.
PeriodUnit = Literal["M", "D"]
# The numpy datetime unit and the name of the calendar period of each
# frequency.
PERIODS: dict[Frequency, tuple[PeriodUnit, str]] = {
    "mon": ("M", "month"),
    "day": ("D", "day"),
}
# The range of the time steps of each frequency, to determine the frequency
# from the data.
TIME_STEPS: dict[Frequency, tuple[np.timedelta64, np.timedelta64]] = {
    "mon": (np.timedelta64(27, "D"), np.timedelta64(32, "D")),
    "day": (np.timedelta64(12, "h"), np.timedelta64(36, "h")),
}


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


def _frequency(
    name: str,
    times: NDArray[np.datetime64],
    bounds: NDArray[np.datetime64] | None,
) -> Frequency:
    """Return the frequency of the time coordinate ``name``.

    The time step is the lower median of the steps between the ``times``,
    so that gaps in the data do not affect it, or the width of the
    ``bounds`` of a single time point.
    """
    if times.size > 1:
        steps = np.sort(np.diff(times))
        step = steps[(steps.size - 1) // 2]
    elif bounds is not None and bounds.shape[0] == 1:
        step = bounds[0, 1] - bounds[0, 0]
    else:
        msg = (
            f"Unable to center {name}: unable to determine its frequency "
            "from a single time point without bounds, set the frequency "
            "option"
        )
        raise ValueError(msg)
    for frequency, (shortest, longest) in TIME_STEPS.items():
        if shortest <= step <= longest:
            return frequency
    days = step / np.timedelta64(1, "D")
    msg = (
        f"Unable to center {name}: unable to determine its frequency from "
        f"its time step of {days:g} days, set the frequency option"
    )
    raise ValueError(msg)


def _periods(
    times: NDArray[np.datetime64], unit: PeriodUnit
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """Return the middle and bounds of the calendar periods of ``times``.

    The periods are given by the numpy datetime ``unit``, e.g. ``M`` for
    months or ``D`` for days.
    """
    start = times.astype(f"datetime64[{unit}]")
    end = start + np.timedelta64(1, unit)
    bounds = np.stack([start, end], axis=1).astype(times.dtype)
    middle = bounds[:, 0] + (bounds[:, 1] - bounds[:, 0]) / 2
    return cast("NDArray[np.datetime64]", middle), bounds


class CenterTimeOptions(Options):
    """Options of :class:`CenterTime`."""

    coordinate: str | None = None
    frequency: Frequency | None = None


class _Correct(NamedTuple):
    """The correct values of a time coordinate and its bounds."""

    name: str
    period: str
    middle: NDArray[np.datetime64]
    bounds: NDArray[np.datetime64]


@register_fix_function
class CenterTime(ConfigurableFix[CenterTimeOptions]):
    """Center time points in the calendar months or days they are in.

    The time coordinate is configured with the ``coordinate`` option, and
    its frequency with the ``frequency`` option, ``mon`` or ``day``. Without
    the ``frequency`` option, the frequency is determined from the time
    steps. The bounds are set to the start of the calendar period of each
    time point and the start of the next period, and the time points to the
    middle of their bounds, as CMIP7 requires for monthly and daily means.
    Coordinates without bounds get a bounds variable named after the
    coordinate with a ``_bnds`` suffix. A coordinate that does not exist, is
    not a dimension coordinate, has an unknown frequency or has two time
    points in the same period raises an error.
    """

    suffix = "center_time"
    name = "Center time"
    description = (
        "Sets the bounds of the time coordinate configured with the "
        "coordinate option to whole calendar months or days, and the time "
        "points to the middle of their period, as CMIP7 requires for "
        "monthly and daily means. The frequency option, mon or day, sets "
        "the period, and is determined from the time steps if it is not "
        "set. Some ESA CCI datasets have time points at the start of the "
        "period, and some have no time bounds."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = CenterTimeOptions

    def _wrong(self, dataset: xr.Dataset) -> _Correct | None:
        """Return the correct coordinate, if it is not correct already."""
        name = self.options.coordinate
        if name is None:
            return None
        if name not in dataset.variables:
            msg = f"Unable to center {name}: it does not exist"
            raise ValueError(msg)
        if dataset[name].dims != (name,):
            msg = f"Unable to center {name}: it is not a dimension coordinate"
            raise ValueError(msg)
        times = _decoded(dataset, name).to_numpy()
        if not np.issubdtype(times.dtype, np.datetime64):
            msg = (
                f"Unable to center {name}: it is not decoded to numpy "
                "datetime64"
            )
            raise ValueError(msg)
        current_bounds = None
        bounds_name = dataset[name].attrs.get("bounds")
        if isinstance(bounds_name, str) and bounds_name in dataset.variables:
            current_bounds = _decoded(dataset, bounds_name, name).to_numpy()
        frequency = self.options.frequency or _frequency(
            name, times, current_bounds
        )
        unit, period = PERIODS[frequency]
        middle, bounds = _periods(times, unit)
        if np.unique(bounds[:, 0]).size != bounds.shape[0]:
            msg = (
                f"Unable to center {name} in calendar {period}s: it has "
                f"several time points in the same {period}"
            )
            raise ValueError(msg)
        if (
            current_bounds is None
            or not np.array_equal(times, middle)
            or not np.array_equal(current_bounds, bounds)
        ):
            return _Correct(name, period, middle, bounds)
        return None

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._wrong(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (correct := self._wrong(dataset)) is None:
            return []
        periods = f"calendar {correct.period}s"
        return [
            (
                f"{correct.name} is not centered in {periods}, or its bounds "
                f"are not whole {periods}"
            )
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (correct := self._wrong(dataset)) is None:
            return False
        if not dry_run:
            name, _, middle, bounds = correct
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
