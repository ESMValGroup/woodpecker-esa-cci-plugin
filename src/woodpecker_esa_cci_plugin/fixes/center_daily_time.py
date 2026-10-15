"""Center ESA CCI daily time points in whole calendar days."""

from __future__ import annotations

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from .center_monthly_time import CenterTimeInPeriods


@register_fix_function
class CenterDailyTime(CenterTimeInPeriods):
    """Center daily time points in the calendar days they are in.

    The daily time coordinate is configured with the ``coordinate`` option.
    Its bounds are set to the start of the calendar day of each time point
    and the start of the next day, and the time points to noon, the middle
    of their bounds, as CMIP7 requires for daily means. Coordinates without
    bounds get a bounds variable named after the coordinate with a ``_bnds``
    suffix. A coordinate that does not exist, is not a dimension coordinate
    or has two time points in the same day raises an error.
    """

    suffix = "center_daily_time"
    name = "Center daily time"
    description = (
        "Sets the bounds of the daily time coordinate configured with the "
        "coordinate option to whole calendar days, and the time points to "
        "noon, the middle of their day, as CMIP7 requires for daily means. "
        "Some ESA CCI daily datasets have time points at the start of the "
        "day, and some have no time bounds."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    unit = "D"
    period = "day"
