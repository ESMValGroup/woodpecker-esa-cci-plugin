"""Select the values of a dimension coordinate of ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import numpy as np
from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .fill_time_gaps import _replace_along

if TYPE_CHECKING:
    import xarray as xr
    from numpy.typing import NDArray

# The relative difference up to which a value of the coordinate matches a
# configured value. Values stored in single precision differ by more than
# the double precision rounding error, e.g. after a unit conversion.
RELATIVE_TOLERANCE = 1e-6


class SelectCoordinateValuesOptions(Options):
    """Options of :class:`SelectCoordinateValues`."""

    coordinate: str | None = None
    values: Annotated[list[float], Field(min_length=1)] | None = None


@register_fix_function
class SelectCoordinateValues(ConfigurableFix[SelectCoordinateValuesOptions]):
    """Select the configured values of a dimension coordinate.

    The coordinate is configured with the ``coordinate`` option, and the
    values to select, in the order of the result, with the ``values``
    option. Values of the coordinate that differ from a configured value by
    up to a relative tolerance of 1e-6 are set to it. The variables along
    the dimension get missing values at the configured values that the
    coordinate does not have, and lose the values at the other values of the
    coordinate. A coordinate that does not exist, is not a dimension
    coordinate or has bounds raises an error, because the bounds of missing
    values are not known.
    """

    suffix = "select_coordinate_values"
    name = "Select coordinate values"
    description = (
        "Selects the values configured with the values option of the "
        "dimension coordinate configured with the coordinate option, in the "
        "configured order. Values of the coordinate that differ from a "
        "configured value by up to a relative tolerance of 1e-6 are set to "
        "it. The variables along the dimension get missing values at the "
        "configured values that the coordinate does not have, and lose the "
        "values at the other values. CMIP7 requires variables on pressure "
        "levels to have exactly the requested levels, e.g. the 39 levels of "
        "plev39, while the ESA CCI ozone profiles have their own levels, of "
        "which many are the same. The values are compared in the units of "
        "the coordinate, so convert it to the units of the configured values "
        "first."
    )
    categories = ["coordinates"]  # noqa: RUF012
    # After unit conversions.
    priority = 45
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = SelectCoordinateValuesOptions

    def _current(self, dataset: xr.Dataset) -> NDArray[np.float64] | None:
        """Return the values of the coordinate, if they need selecting."""
        name = self.options.coordinate
        values = self.options.values
        if name is None or values is None:
            return None
        action = f"Unable to select the values of {name}"
        if name not in dataset.variables:
            msg = f"{action}: it does not exist"
            raise ValueError(msg)
        if dataset[name].dims != (name,):
            msg = f"{action}: it is not a dimension coordinate"
            raise ValueError(msg)
        if "bounds" in dataset[name].attrs:
            msg = f"{action}: it has bounds"
            raise ValueError(msg)
        current = dataset[name].to_numpy().astype(np.float64)
        if np.array_equal(current, values):
            return None
        return current

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._current(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if self._current(dataset) is None:
            return []
        return [
            f"{self.options.coordinate} does not have the configured values"
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (current := self._current(dataset)) is None:
            return False
        if not dry_run:
            name = str(self.options.coordinate)
            values = np.asarray(self.options.values, dtype=np.float64)
            matched = current.copy()
            for value in values:
                matched[
                    np.isclose(current, value, rtol=RELATIVE_TOLERANCE, atol=0)
                ] = value
            coordinate = dataset[name].variable
            renamed = dataset.assign_coords(
                {name: coordinate.copy(data=matched)}
            )
            _replace_along(dataset, renamed.reindex({name: values}), name)
        return True
