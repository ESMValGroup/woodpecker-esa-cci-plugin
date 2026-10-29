"""Add bounds to ESA CCI coordinates on a regular grid."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import (
    ConfigurableFix,
    NonEmptyNames,
    Options,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

# The name of the dimension of the two bounds of each cell.
BOUNDS_DIMENSION = "bnds"
# The maximum difference between steps, relative to the step size, that
# counts as a fixed step. Coordinates stored in single precision differ by
# much less than this.
STEP_TOLERANCE = 1e-3


def _bounds(
    name: str,
    values: NDArray[np.floating],
    *,
    varying_step: bool = False,
) -> NDArray[np.floating]:
    """Return the bounds of the cells centered on ``values``.

    With ``varying_step``, the bounds are halfway between the values, and
    the outer bounds half a step beyond the first and last value.
    """
    if values.size < 2:  # noqa: PLR2004
        msg = f"Unable to add bounds to {name}: it has less than 2 values"
        raise ValueError(msg)
    steps = np.diff(values)
    if varying_step:
        edges = np.concatenate(
            [
                [values[0] - steps[0] / 2],
                values[:-1] + steps / 2,
                [values[-1] + steps[-1] / 2],
            ]
        )
        return np.stack([edges[:-1], edges[1:]], axis=1)
    step = (values[-1] - values[0]) / (values.size - 1)
    if not np.allclose(steps, step, rtol=0, atol=STEP_TOLERANCE * abs(step)):
        msg = f"Unable to add bounds to {name}: its step size is not fixed"
        raise ValueError(msg)
    return np.stack([values - step / 2, values + step / 2], axis=1)


class AddBoundsOptions(Options):
    """Options of :class:`AddBounds`."""

    coordinates: NonEmptyNames | None = None
    varying_step: NonEmptyNames | None = None


@register_fix_function
class AddBounds(ConfigurableFix[AddBoundsOptions]):
    """Add bounds to coordinates with a fixed step size.

    The coordinates are configured with the ``coordinates`` option, a list of
    dimension coordinate names. Coordinates without a ``bounds`` attribute
    get a bounds variable named after the coordinate with a ``_bnds``
    suffix, with cells that are centered on the coordinate values and as
    wide as the step size. The coordinates in the ``varying_step`` option
    may have a step size that varies, and get bounds halfway between their
    values instead. Coordinates that do not exist, are not dimension
    coordinates or do not have a fixed step size raise an error.
    """

    suffix = "add_bounds"
    name = "Add bounds"
    description = (
        "Adds bounds to the dimension coordinates configured with the "
        "coordinates option, a list of coordinate names, if they have none. "
        "The cells are centered on the coordinate values and as wide as the "
        "fixed step size of the coordinate. The coordinates in the "
        "varying_step option, e.g. the latitudes of an EASE-Grid 2.0, may "
        "have a step size that varies, and get bounds halfway between their "
        "values instead, which approximates the cells of a grid whose step "
        "size varies slowly."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = AddBoundsOptions

    def _wrong(self, dataset: xr.Dataset) -> list[str]:
        wrong = []
        for name in self.options.coordinates or []:
            if name not in dataset.variables:
                msg = f"Unable to add bounds to {name}: it does not exist"
                raise ValueError(msg)
            if dataset[name].dims != (name,):
                msg = (
                    f"Unable to add bounds to {name}: it is not a dimension "
                    "coordinate"
                )
                raise ValueError(msg)
            if "bounds" not in dataset[name].attrs:
                if f"{name}_bnds" in dataset.variables:
                    msg = (
                        f"Unable to add bounds to {name}: {name}_bnds already "
                        "exists"
                    )
                    raise ValueError(msg)
                # Raise an error now if the bounds cannot be computed.
                self._bounds(dataset, name)
                wrong.append(name)
        return wrong

    def _bounds(self, dataset: xr.Dataset, name: str) -> NDArray[np.floating]:
        varying_step = name in (self.options.varying_step or [])
        return _bounds(
            name, dataset[name].to_numpy(), varying_step=varying_step
        )

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [f"{name} has no bounds" for name in self._wrong(dataset)]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name in wrong:
                bounds = f"{name}_bnds"
                dataset[bounds] = xr.Variable(
                    (name, BOUNDS_DIMENSION), self._bounds(dataset, name)
                )
                dataset[name].attrs["bounds"] = bounds
        return bool(wrong)
