"""Wrap ESA CCI longitudes to the range [0, 360)."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import numpy as np
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import FixFunction, register_fix_function

if TYPE_CHECKING:
    import xarray as xr

# Valid range attributes of the wrapped longitude and bounds.
VALID_RANGE = {
    "valid_range": [0.0, 360.0],
    "valid_min": 0.0,
    "valid_max": 360.0,
}


@register_fix_function
class NormalizeLongitude(FixFunction):
    """Wrap a longitude coordinate to the range [0, 360).

    The longitude dimension coordinate is configured with the ``coordinate``
    option. Its values and bounds are wrapped to [0, 360) and all variables
    along it are reordered, so the coordinate stays increasing. Their
    ``valid_range``, ``valid_min`` and ``valid_max`` attributes, if present,
    are updated to match. Unlike the core woodpecker
    ``normalize_longitude_convention`` fix, this keeps the coordinate
    monotonic. A coordinate that does not exist or is not a dimension
    coordinate raises an error.
    """

    suffix = "normalize_longitude"
    name = "Normalize longitude"
    description = (
        "Wraps the configured longitude coordinate and its bounds to "
        "[0, 360) and reorders the data so the coordinate stays increasing."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012

    def _coordinate(self, dataset: xr.Dataset) -> str | None:
        name = self.config.get("coordinate")
        if name is None:
            return None
        if not isinstance(name, str):
            msg = "The coordinate option must be a string"
            raise TypeError(msg)
        if name not in dataset.variables:
            msg = f"Unable to normalize {name}: it does not exist"
            raise ValueError(msg)
        if dataset[name].dims != (name,):
            msg = (
                f"Unable to normalize {name}: it is not a dimension coordinate"
            )
            raise ValueError(msg)
        return name

    def _wrong(self, dataset: xr.Dataset) -> str | None:
        name = self._coordinate(dataset)
        if name is None:
            return None
        lon = dataset[name].to_numpy()
        if ((lon < 0) | (lon >= 360)).any():  # noqa: PLR2004
            return name
        return None

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._wrong(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (name := self._wrong(dataset)) is None:
            return []
        return [f"{name} has values outside the range [0, 360)"]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (name := self._wrong(dataset)) is None:
            return False
        if not dry_run:
            _wrap(dataset, name)
        return True


def _set_valid_range(variable: xr.Variable) -> None:
    """Update the valid range attributes of ``variable`` to [0, 360]."""
    # Otherwise, readers that apply the valid range mask the wrapped values.
    for key, value in VALID_RANGE.items():
        if key in variable.attrs:
            variable.attrs[key] = copy.deepcopy(value)


def _wrap(dataset: xr.Dataset, name: str) -> None:
    """Wrap longitude ``name`` in ``dataset`` to [0, 360) in place."""
    lon = dataset[name].to_numpy()
    offset = lon % 360 - lon
    order = np.argsort(lon + offset, kind="stable")
    offset = offset[order]
    wrapped = dataset.isel({name: order})

    coordinate = wrapped[name].variable
    data = (coordinate.data + offset).astype(coordinate.dtype)
    coordinate = coordinate.copy(data=data)
    _set_valid_range(coordinate)
    dataset.coords[name] = coordinate
    bounds = dataset[name].attrs.get("bounds")
    for var in list(dataset.variables):
        if var == name or name not in dataset[var].dims:
            continue
        variable = wrapped[var].variable
        if var == bounds:
            # Shift both bounds of a cell by the offset of its center, so
            # cells that cross 0 or 360 keep their width.
            shift = np.expand_dims(offset, axis=1 - variable.dims.index(name))
            data = (variable.data + shift).astype(variable.dtype)
            variable = variable.copy(data=data)
            _set_valid_range(variable)
        if var in dataset.coords:
            dataset.coords[var] = variable
        else:
            dataset[var] = variable
