"""Add bounds to the coordinates of ESA CCI grids."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from pyproj import CRS, Transformer
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
# The name of the dimension of the four vertices of each cell.
VERTICES_DIMENSION = "vertices"
# The maximum difference between steps, relative to the step size, that
# counts as a fixed step. Coordinates stored in single precision differ by
# much less than this.
STEP_TOLERANCE = 1e-3
# The standard names of the projection coordinates, by axis.
PROJECTION_COORDINATES = {
    "x": "projection_x_coordinate",
    "y": "projection_y_coordinate",
}
# The units of the projection coordinates that pyproj expects.
PROJECTION_UNITS = "m"
# The units that CF allows for latitudes and longitudes:
# https://cfconventions.org/cf-conventions/cf-conventions.html#latitude-coordinate
LATITUDE_UNITS = {
    "degrees_north",
    "degree_north",
    "degree_N",
    "degrees_N",
    "degreeN",
    "degreesN",
}
LONGITUDE_UNITS = {
    "degrees_east",
    "degree_east",
    "degree_E",
    "degrees_E",
    "degreeE",
    "degreesE",
}


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
    grid_mapping: str | None = None


@register_fix_function
class AddBounds(ConfigurableFix[AddBoundsOptions]):
    """Add bounds to dimension coordinates and 2-D latitudes and longitudes.

    The coordinates are configured with the ``coordinates`` option, a list of
    coordinate names. Coordinates without a ``bounds`` attribute get a bounds
    variable named after the coordinate with a ``_bnds`` suffix.

    The cells of dimension coordinates are centered on the coordinate values
    and as wide as the step size. The coordinates in the ``varying_step``
    option may have a step size that varies, and get bounds halfway between
    their values instead.

    The 2-D latitudes and longitudes of a projected grid need the grid mapping
    variable of the grid, configured with the ``grid_mapping`` option, and
    are told apart by their units. Their dimensions must be the projection x
    and y coordinates, in m, which either have bounds or are in
    ``coordinates`` too. The corners of each cell are transformed from the
    projection to latitude and longitude with pyproj, with the four vertices
    anticlockwise, as CF recommends.

    Coordinates that do not exist or whose bounds cannot be computed raise an
    error.
    """

    suffix = "add_bounds"
    name = "Add bounds"
    description = (
        "Adds bounds to the coordinates configured with the coordinates "
        "option, a list of coordinate names, if they have none. The cells of "
        "dimension coordinates are centered on the coordinate values and as "
        "wide as the fixed step size of the coordinate. The coordinates in "
        "the varying_step option, e.g. the latitudes of an EASE-Grid 2.0, may "
        "have a step size that varies, and get bounds halfway between their "
        "values instead, which approximates the cells of a grid whose step "
        "size varies slowly. The bounds of the 2-D latitudes and longitudes "
        "of a projected grid are computed from the bounds of the projection "
        "x and y coordinates, which must be in m and either have bounds or "
        "be in the coordinates option too, and transformed to latitude and "
        "longitude with pyproj, using the CF grid mapping variable configured "
        "with the grid_mapping option. Unlike bounds interpolated from the "
        "latitudes and longitudes, these are also correct near the pole and "
        "across the antimeridian."
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
            coordinate = dataset[name]
            if coordinate.dims != (name,) and coordinate.ndim != 2:  # noqa: PLR2004
                msg = (
                    f"Unable to add bounds to {name}: it is not a dimension "
                    "coordinate or a 2-D coordinate"
                )
                raise ValueError(msg)
            if "bounds" not in coordinate.attrs:
                if f"{name}_bnds" in dataset.variables:
                    msg = (
                        f"Unable to add bounds to {name}: {name}_bnds already "
                        "exists"
                    )
                    raise ValueError(msg)
                # Raise an error now if the bounds cannot be computed.
                if coordinate.ndim == 1:
                    self._dimension_bounds(dataset, name)
                else:
                    self._grid_mapping(dataset, name)
                    self._is_longitude(dataset, name)
                    self._projection_bounds(dataset, name)
                wrong.append(name)
        return wrong

    def _dimension_bounds(
        self, dataset: xr.Dataset, name: str
    ) -> NDArray[np.floating]:
        varying_step = name in (self.options.varying_step or [])
        return _bounds(
            name, dataset[name].to_numpy(), varying_step=varying_step
        )

    def _is_longitude(self, dataset: xr.Dataset, name: str) -> bool:
        units = dataset[name].attrs.get("units")
        if units not in LATITUDE_UNITS | LONGITUDE_UNITS:
            msg = (
                f"Unable to add bounds to {name}: its units, {units}, are not "
                "those of a latitude or longitude"
            )
            raise ValueError(msg)
        return units in LONGITUDE_UNITS

    def _grid_mapping(self, dataset: xr.Dataset, name: str) -> xr.DataArray:
        grid_mapping = self.options.grid_mapping
        if grid_mapping is None:
            msg = (
                f"Unable to add bounds to {name}: a 2-D coordinate needs the "
                "grid_mapping option"
            )
            raise ValueError(msg)
        if grid_mapping not in dataset.variables:
            msg = (
                f"Unable to add bounds to {name}: {grid_mapping} does not "
                "exist"
            )
            raise ValueError(msg)
        return dataset[grid_mapping]

    def _projection_bounds(
        self, dataset: xr.Dataset, name: str
    ) -> dict[str, xr.DataArray]:
        """Return the bounds of the projection coordinates, by axis."""
        bounds = {}
        dims = dataset[name].dims
        for axis, standard_name in PROJECTION_COORDINATES.items():
            found = [
                dim
                for dim in dims
                if dim in dataset.variables
                and dataset[dim].attrs.get("standard_name") == standard_name
            ]
            if not found:
                msg = (
                    f"Unable to add bounds to {name}: none of its "
                    f"dimensions is a {standard_name}"
                )
                raise ValueError(msg)
            dim = str(found[0])
            attrs = dataset[dim].attrs
            if attrs.get("units") != PROJECTION_UNITS:
                msg = (
                    f"Unable to add bounds to {name}: {dim} is not in "
                    f"{PROJECTION_UNITS}"
                )
                raise ValueError(msg)
            if attrs.get("bounds") in dataset.variables:
                bounds[axis] = dataset[attrs["bounds"]]
            elif dim in (self.options.coordinates or []):
                bounds[axis] = xr.DataArray(
                    self._dimension_bounds(dataset, dim),
                    dims=(dim, BOUNDS_DIMENSION),
                )
            else:
                msg = f"Unable to add bounds to {name}: {dim} has no bounds"
                raise ValueError(msg)
        return bounds

    def _geographic_bounds(
        self, dataset: xr.Dataset, name: str
    ) -> xr.Variable:
        """Return the bounds of the 2-D latitude or longitude ``name``."""
        lower = {}
        upper = {}
        for axis, bounds in self._projection_bounds(dataset, name).items():
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
        dims = (*dataset[name].dims, VERTICES_DIMENSION)
        x = xr.concat([c[0] for c in corners], VERTICES_DIMENSION)
        y = xr.concat([c[1] for c in corners], VERTICES_DIMENSION)
        x, y = xr.broadcast(x, y)
        x = x.transpose(*dims)
        y = y.transpose(*dims)
        crs = CRS.from_cf(self._grid_mapping(dataset, name).attrs)
        transformer = Transformer.from_crs(
            crs, crs.geodetic_crs, always_xy=True
        )
        lon_bnds, lat_bnds = transformer.transform(x.to_numpy(), y.to_numpy())
        if not self._is_longitude(dataset, name):
            return xr.Variable(dims, lat_bnds)
        # pyproj returns longitudes in [-180, 180], so the vertices of cells
        # that cross the antimeridian are 360 degrees apart. Keep them within
        # 180 degrees of the center of the cell instead.
        lon = dataset[name].to_numpy()[..., np.newaxis]
        return xr.Variable(dims, lon + (lon_bnds - lon + 180) % 360 - 180)

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
                if dataset[name].ndim == 1:
                    dataset[bounds] = xr.Variable(
                        (name, BOUNDS_DIMENSION),
                        self._dimension_bounds(dataset, name),
                    )
                else:
                    dataset[bounds] = self._geographic_bounds(dataset, name)
                dataset[name].attrs["bounds"] = bounds
        return bool(wrong)
