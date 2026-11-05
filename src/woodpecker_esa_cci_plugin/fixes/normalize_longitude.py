"""Wrap ESA CCI longitudes to the range [0, 360)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .remove_range_attributes import remove_range_attributes

if TYPE_CHECKING:
    import xarray as xr


class NormalizeLongitudeOptions(Options):
    """Options of :class:`NormalizeLongitude`."""

    coordinate: str | None = None


@register_fix_function
class NormalizeLongitude(ConfigurableFix[NormalizeLongitudeOptions]):
    """Wrap a longitude coordinate to the range [0, 360).

    The longitude coordinate is configured with the ``coordinate`` option.
    Its values and bounds are wrapped to [0, 360). For a dimension
    coordinate, all variables along it are reordered, so the coordinate
    stays increasing. A 2-D longitude of a projected grid is wrapped without
    reordering. The bounds of each cell are shifted by the offset of its
    center, so cells that cross 0 or 360 keep their width. The range
    attributes of the coordinate and bounds, such as ``valid_range``, are
    removed, because they no longer match. Unlike the core woodpecker
    ``normalize_longitude_convention`` fix, this keeps the coordinate
    monotonic. A coordinate that does not exist, or that is 1-D but not a
    dimension coordinate, raises an error.
    """

    suffix = "normalize_longitude"
    name = "Normalize longitude"
    description = (
        "Wraps the longitude coordinate configured with the coordinate "
        "option, and its bounds, to [0, 360). A dimension coordinate is "
        "reordered with the data so it stays increasing, and a 2-D longitude "
        "of a projected grid is wrapped in place. Their range attributes, "
        "such as valid_range, are removed. Unlike the core woodpecker "
        "normalize_longitude_convention fix, the result is monotonic."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = NormalizeLongitudeOptions

    def _coordinate(self, dataset: xr.Dataset) -> str | None:
        name = self.options.coordinate
        if name is None:
            return None
        if name not in dataset.variables:
            msg = f"Unable to normalize {name}: it does not exist"
            raise ValueError(msg)
        dims = dataset[name].dims
        if len(dims) != 2 and dims != (name,):  # noqa: PLR2004
            msg = (
                f"Unable to normalize {name}: it is not a dimension "
                "coordinate or a 2-D coordinate"
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
            if dataset[name].ndim == 1:
                _wrap(dataset, name)
            else:
                _wrap_2d(dataset, name)
        return True


def _wrap_2d(dataset: xr.Dataset, name: str) -> None:
    """Wrap 2-D longitude ``name`` in ``dataset`` to [0, 360) in place."""
    coordinate = dataset[name].variable
    offset = coordinate.data % 360 - coordinate.data
    data = (coordinate.data + offset).astype(coordinate.dtype)
    coordinate = coordinate.copy(data=data)
    remove_range_attributes(coordinate)
    dataset.coords[name] = coordinate
    bounds = coordinate.attrs.get("bounds")
    if bounds in dataset.variables:
        variable = dataset[bounds].variable
        # The vertices are the last dimension of the bounds.
        shift = offset[..., np.newaxis]
        data = (variable.data + shift).astype(variable.dtype)
        variable = variable.copy(data=data)
        remove_range_attributes(variable)
        dataset[bounds] = variable


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
    remove_range_attributes(coordinate)
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
            remove_range_attributes(variable)
        if var in dataset.coords:
            dataset.coords[var] = variable
        else:
            dataset[var] = variable
