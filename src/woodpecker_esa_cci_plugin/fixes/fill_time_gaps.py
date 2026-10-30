"""Fill gaps in the time coordinate of ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import xarray as xr
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .center_time import (
    PERIODS,
    Frequency,
    _decoded,
    _encoded,
    _frequency,
    _periods,
)
from .set_time_units import _is_decoded

if TYPE_CHECKING:
    from collections.abc import Hashable

    from numpy.typing import NDArray


class FillTimeGapsOptions(Options):
    """Options of :class:`FillTimeGaps`."""

    coordinate: str | None = None
    frequency: Frequency | None = None


class _Gaps(NamedTuple):
    """The time points of a time coordinate with its gaps filled."""

    name: str
    period: str
    missing: int
    middle: NDArray[np.datetime64]
    bounds: NDArray[np.datetime64]


@register_fix_function
class FillTimeGaps(ConfigurableFix[FillTimeGapsOptions]):
    """Add the missing calendar months or days to a time coordinate.

    The time coordinate is configured with the ``coordinate`` option, and
    its frequency with the ``frequency`` option, ``mon`` or ``day``. Without
    the ``frequency`` option, the frequency is determined from the time
    steps. Each calendar period between the first and the last time point
    that has no time point gets one, in the middle of the period, with
    bounds at the start of the period and the start of the next one, like
    the ``center_time`` fix sets them. The variables along the time
    dimension are missing at the added time points. A coordinate that does
    not exist, is not a dimension coordinate or has an unknown frequency
    raises an error.
    """

    suffix = "fill_time_gaps"
    name = "Fill time gaps"
    description = (
        "Adds a time point, with missing values, for each calendar month or "
        "day without data between the first and the last time point of the "
        "time coordinate configured with the coordinate option, as CMIP7 "
        "requires a time coordinate without gaps. The frequency option, mon "
        "or day, sets the period, and is determined from the time steps if "
        "it is not set. Run it after esa_cci.center_time, which sets the "
        "time points and bounds of the existing periods. Some ESA CCI "
        "datasets leave out the months in which no satellite was available, "
        "while the same dataset in the Open Data Portal store has them, "
        "with missing values."
    )
    categories = ["coordinates"]  # noqa: RUF012
    # After esa_cci.center_time.
    priority = 49
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = FillTimeGapsOptions

    def _gaps(self, dataset: xr.Dataset) -> _Gaps | None:
        """Return the time points without gaps, if there are gaps."""
        name = self.options.coordinate
        if name is None:
            return None
        if name not in dataset.variables:
            msg = f"Unable to fill the gaps in {name}: it does not exist"
            raise ValueError(msg)
        if dataset[name].dims != (name,):
            msg = (
                f"Unable to fill the gaps in {name}: it is not a dimension "
                "coordinate"
            )
            raise ValueError(msg)
        times = _decoded(dataset, name).to_numpy()
        if times.size == 0:
            return None
        frequency = self.options.frequency or _frequency(name, times, None)
        unit, period = PERIODS[frequency]
        starts = np.unique(times.astype(f"datetime64[{unit}]"))
        every = np.arange(starts[0], starts[-1] + np.timedelta64(1, unit))
        missing = every.size - starts.size
        if not missing:
            return None
        middle, bounds = _periods(every.astype(times.dtype), unit)
        return _Gaps(name, period, missing, middle, bounds)

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._gaps(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (gaps := self._gaps(dataset)) is None:
            return []
        return [
            f"{gaps.name} has no time point in {gaps.missing} {gaps.period}s"
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (gaps := self._gaps(dataset)) is None:
            return False
        if not dry_run:
            _fill(dataset, gaps)
        return True


def _fill(dataset: xr.Dataset, gaps: _Gaps) -> None:
    """Add the time points of ``gaps`` to ``dataset`` in place."""
    name = gaps.name
    variable = dataset[name].variable
    times = gaps.middle
    if not _is_decoded(variable):
        # Reindex with the encoded times, like the existing ones.
        decoded = _decoded(dataset, name)
        times = _encoded(
            variable, _resized(decoded, (name,), times), times, name
        ).to_numpy()
    # The existing time points are the middles of their periods, so they
    # are kept exactly, and the added ones are missing.
    filled = dataset.reindex({name: times})
    filled[name].attrs = variable.attrs
    filled[name].encoding = variable.encoding
    bounds_name = variable.attrs.get("bounds")
    if isinstance(bounds_name, str) and bounds_name in dataset.variables:
        original = dataset[bounds_name].variable
        bounds = gaps.bounds
        if original.dims[0] != name:
            bounds = bounds.T
        decoded_bounds = _resized(
            _decoded(dataset, bounds_name, name), original.dims, bounds
        )
        filled[bounds_name] = _encoded(
            original, decoded_bounds, bounds, bounds_name
        )
    _replace_along(dataset, filled, name)


def _replace_along(
    dataset: xr.Dataset, replacement: xr.Dataset, dimension: str
) -> None:
    """Replace the variables along ``dimension`` in place.

    The variables of ``dataset`` along ``dimension`` are replaced by those
    of ``replacement``, which has a different length along it.
    """
    names = [
        var for var in dataset.variables if dimension in dataset[var].dims
    ]
    coords = [var for var in names if var in dataset.coords]
    for var in names:
        del dataset[var]
    dataset.update(replacement[[var for var in names if var not in coords]])
    dataset.coords.update(replacement[coords].coords)


def _resized(
    variable: xr.Variable,
    dims: tuple[Hashable, ...],
    values: NDArray[np.datetime64],
) -> xr.Variable:
    """Return ``variable`` with the decoded times ``values``."""
    return xr.Variable(
        dims,
        values,
        attrs=variable.attrs,
        encoding=dict(variable.encoding),
    )
