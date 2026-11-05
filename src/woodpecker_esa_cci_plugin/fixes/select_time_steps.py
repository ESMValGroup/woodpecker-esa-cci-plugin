"""Select the time steps on a day of the month in ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import numpy as np
from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .center_time import _decoded
from .fill_time_gaps import _replace_along

if TYPE_CHECKING:
    import xarray as xr
    from numpy.typing import NDArray


class SelectTimeStepsOptions(Options):
    """Options of :class:`SelectTimeSteps`."""

    coordinate: str | None = None
    day_of_month: Annotated[int, Field(ge=1, le=31)] | None = None


@register_fix_function
class SelectTimeSteps(ConfigurableFix[SelectTimeStepsOptions]):
    """Keep only the time steps on a day of the month.

    The time coordinate is configured with the ``coordinate`` option, and
    the day of the month of the time points to keep with the
    ``day_of_month`` option. The variables along the time dimension are
    removed at the other time points. A coordinate that does not exist or
    is not a dimension coordinate raises an error.
    """

    suffix = "select_time_steps"
    name = "Select time steps"
    description = (
        "Keeps only the time points of the time coordinate configured with "
        "the coordinate option that are on the day of the month configured "
        "with the day_of_month option, and removes the other time steps. "
        "Some ESA CCI datasets have overlapping 30-day means every 15 days, "
        "on the 1st and the 15th of each month. Those on the 15th are close "
        "to the monthly means that CMIP7 uses, and do not overlap. Run it "
        "before esa_cci.center_time, which then sets the time points and "
        "bounds of the months."
    )
    categories = ["coordinates"]  # noqa: RUF012
    # Before esa_cci.center_time.
    priority = 45
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = SelectTimeStepsOptions

    def _selected(self, dataset: xr.Dataset) -> NDArray[np.bool_] | None:
        """Return which time steps to keep, if not all of them."""
        name = self.options.coordinate
        day = self.options.day_of_month
        if name is None or day is None:
            return None
        if name not in dataset.variables:
            msg = (
                f"Unable to select the time steps of {name}: it does not exist"
            )
            raise ValueError(msg)
        if dataset[name].dims != (name,):
            msg = (
                f"Unable to select the time steps of {name}: it is not a "
                "dimension coordinate"
            )
            raise ValueError(msg)
        times = _decoded(dataset, name).to_numpy()
        days = times.astype("datetime64[D]") - times.astype("datetime64[M]")
        selected: NDArray[np.bool_] = days == np.timedelta64(day - 1, "D")
        if selected.all():
            return None
        return selected

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._selected(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (selected := self._selected(dataset)) is None:
            return []
        return [
            (
                f"{self.options.coordinate} has "
                f"{np.count_nonzero(~selected)} time points that are not on "
                f"day {self.options.day_of_month} of the month"
            ),
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (selected := self._selected(dataset)) is None:
            return False
        if not dry_run:
            name = str(self.options.coordinate)
            _replace_along(dataset, dataset.isel({name: selected}), name)
        return True
