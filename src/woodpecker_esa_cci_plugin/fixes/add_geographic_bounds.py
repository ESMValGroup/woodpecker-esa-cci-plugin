"""Add bounds to the latitudes and longitudes of projected ESA CCI grids."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import numpy as np
import xarray as xr
from pydantic import model_validator
from pyproj import CRS, Transformer
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    from numpy.typing import NDArray

# The name of the dimension of the four vertices of each cell.
VERTICES_DIMENSION = "vertices"
# The standard names of the projection coordinates, by axis.
PROJECTION_COORDINATES = {
    "x": "projection_x_coordinate",
    "y": "projection_y_coordinate",
}
# The units of the projection coordinates that pyproj expects.
PROJECTION_UNITS = "m"


class AddGeographicBoundsOptions(Options):
    """Options of :class:`AddGeographicBounds`."""

    latitude: str | None = None
    longitude: str | None = None
    grid_mapping: str | None = None

    @model_validator(mode="after")
    def _all_or_none(self) -> Self:
        names = (self.latitude, self.longitude, self.grid_mapping)
        if any(name is None for name in names) and any(
            name is not None for name in names
        ):
            msg = (
                "The latitude, longitude and grid_mapping options must all be "
                "set"
            )
            raise ValueError(msg)
        return self


@register_fix_function
class AddGeographicBounds(ConfigurableFix[AddGeographicBoundsOptions]):
    """Add bounds to the 2-D latitudes and longitudes of a projected grid.

    The 2-D latitude and longitude coordinates are configured with the
    ``latitude`` and ``longitude`` options, and the grid mapping variable of
    the grid with the ``grid_mapping`` option. The dimensions of the
    latitudes must be the projection x and y coordinates, which need bounds
    in m, e.g. from ``esa_cci.add_bounds``. The corners of each cell are
    transformed from the projection to latitude and longitude with pyproj,
    and stored in bounds variables named after the coordinates with a
    ``_bnds`` suffix, with the four vertices anticlockwise, as CF
    recommends. Coordinates that already have bounds are left unchanged.
    """

    suffix = "add_geographic_bounds"
    name = "Add geographic bounds"
    description = (
        "Adds bounds to the 2-D latitude and longitude coordinates of a "
        "projected grid, configured with the latitude and longitude options, "
        "if they have none. The corners of the cells are computed from the "
        "bounds of the projection x and y coordinates, which must be in m, "
        "and transformed to latitude and longitude with pyproj, using the CF "
        "grid mapping variable configured with the grid_mapping option. "
        "Unlike bounds interpolated from the latitudes and longitudes, these "
        "are also correct near the pole and across the antimeridian."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = AddGeographicBoundsOptions

    def _names(self) -> tuple[str, str, str] | None:
        latitude = self.options.latitude
        longitude = self.options.longitude
        grid_mapping = self.options.grid_mapping
        if latitude is None or longitude is None or grid_mapping is None:
            return None
        return latitude, longitude, grid_mapping

    def _projection_bounds(
        self, dataset: xr.Dataset, latitude: str
    ) -> dict[str, xr.DataArray]:
        """Return the bounds of the projection coordinates, by axis."""
        bounds = {}
        dims = dataset[latitude].dims
        for axis, standard_name in PROJECTION_COORDINATES.items():
            found = [
                dim
                for dim in dims
                if dim in dataset.variables
                and dataset[dim].attrs.get("standard_name") == standard_name
            ]
            if not found:
                msg = (
                    f"Unable to add bounds to {latitude}: none of its "
                    f"dimensions is a {standard_name}"
                )
                raise ValueError(msg)
            name = found[0]
            attrs = dataset[name].attrs
            if attrs.get("units") != PROJECTION_UNITS:
                msg = (
                    f"Unable to add bounds to {latitude}: {name} is not in "
                    f"{PROJECTION_UNITS}"
                )
                raise ValueError(msg)
            if attrs.get("bounds") not in dataset.variables:
                msg = (
                    f"Unable to add bounds to {latitude}: {name} has no bounds"
                )
                raise ValueError(msg)
            bounds[axis] = dataset[attrs["bounds"]]
        return bounds

    def _wrong(self, dataset: xr.Dataset) -> list[str]:
        names = self._names()
        if names is None:
            return []
        for name in names:
            if name not in dataset.variables:
                msg = f"Unable to add geographic bounds: {name} does not exist"
                raise ValueError(msg)
        latitude, longitude, _ = names
        if dataset[latitude].ndim != 2 or (  # noqa: PLR2004
            dataset[longitude].dims != dataset[latitude].dims
        ):
            msg = (
                f"Unable to add bounds to {latitude} and {longitude}: they "
                "are not 2-D coordinates with the same dimensions"
            )
            raise ValueError(msg)
        wrong = []
        for name in (latitude, longitude):
            if "bounds" not in dataset[name].attrs:
                if f"{name}_bnds" in dataset.variables:
                    msg = (
                        f"Unable to add bounds to {name}: {name}_bnds already "
                        "exists"
                    )
                    raise ValueError(msg)
                wrong.append(name)
        if wrong:
            # Raise an error now if the bounds cannot be computed.
            self._projection_bounds(dataset, latitude)
        return wrong

    def _bounds(
        self, dataset: xr.Dataset
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], tuple[Hashable, ...]]:
        """Return the latitude and longitude bounds and their dimensions."""
        names = self._names()
        assert names is not None  # noqa: S101
        latitude, longitude, grid_mapping = names
        projection_bounds = self._projection_bounds(dataset, latitude)
        lower = {}
        upper = {}
        for axis, bounds in projection_bounds.items():
            values = bounds.to_numpy()
            # The bounds may decrease along the coordinate.
            lower[axis] = xr.DataArray(
                values.min(axis=1), dims=bounds.dims[:1]
            )
            upper[axis] = xr.DataArray(
                values.max(axis=1), dims=bounds.dims[:1]
            )
        # Anticlockwise in the x-y plane, which keeps the orientation on the
        # Earth for the projections of the ESA CCI grids.
        corners = [
            (lower["x"], lower["y"]),
            (upper["x"], lower["y"]),
            (upper["x"], upper["y"]),
            (lower["x"], upper["y"]),
        ]
        dims = (*dataset[latitude].dims, VERTICES_DIMENSION)
        x = xr.concat([c[0] for c in corners], VERTICES_DIMENSION)
        y = xr.concat([c[1] for c in corners], VERTICES_DIMENSION)
        x, y = xr.broadcast(x, y)
        x = x.transpose(*dims)
        y = y.transpose(*dims)
        crs = CRS.from_cf(dataset[grid_mapping].attrs)
        transformer = Transformer.from_crs(
            crs, crs.geodetic_crs, always_xy=True
        )
        lon_bnds, lat_bnds = transformer.transform(x.to_numpy(), y.to_numpy())
        # pyproj returns longitudes in [-180, 180], so the vertices of cells
        # that cross the antimeridian are 360 degrees apart. Keep them within
        # 180 degrees of the center of the cell instead.
        lon = dataset[longitude].to_numpy()[..., np.newaxis]
        lon_bnds = lon + (lon_bnds - lon + 180) % 360 - 180
        return lat_bnds, lon_bnds, dims

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
        names = self._names()
        if not dry_run and wrong and names is not None:
            latitude, longitude, _ = names
            lat_bnds, lon_bnds, dims = self._bounds(dataset)
            for name, values in ((latitude, lat_bnds), (longitude, lon_bnds)):
                if name in wrong:
                    bounds = f"{name}_bnds"
                    dataset[bounds] = xr.Variable(dims, values)
                    dataset[name].attrs["bounds"] = bounds
        return bool(wrong)
