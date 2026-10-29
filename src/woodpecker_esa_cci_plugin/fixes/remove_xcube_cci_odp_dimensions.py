"""Remove the dimensions that the xcube-cci Open Data Portal store adds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import (
    ConfigurableFix,
    NonEmptyNames,
    Options,
)

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# The attribute in which the xcube-cci Open Data Portal store lists the
# dimensions of a variable in the original files.
FILE_DIMENSIONS = "file_dimensions"
# The names that the store gives to dimensions of the original files. It
# names latitude_centers, the latitudes of zonal means, lat, and adds a lon
# dimension.
DIMENSION_NAMES = {
    "latitude": "lat",
    "latitude_centers": "lat",
    "longitude": "lon",
}


class RemoveXcubeCciOdpDimensionsOptions(Options):
    """Options of :class:`RemoveXcubeCciOdpDimensions`."""

    dimensions: NonEmptyNames | None = None


@register_fix_function
class RemoveXcubeCciOdpDimensions(
    ConfigurableFix[RemoveXcubeCciOdpDimensionsOptions]
):
    """Remove the dimensions that the Open Data Portal store adds.

    The xcube-cci Open Data Portal store opens a netCDF file for each time
    step and stacks the variables along time, also the variables that the
    files store without a time dimension, such as 2-D latitudes and
    longitudes. It also adds a longitude dimension to zonal means. The
    dimensions to remove are configured with the ``dimensions`` option, a
    list of dimension names. Variables with one of them that is not in their
    ``file_dimensions`` attribute are replaced by their first index along
    it, because the store repeats the same values. Some datasets store each
    time step in a file without a time dimension, so only the configured
    dimensions are removed. Datasets from other stores do not have the
    attribute, so the fix does nothing for those. It must run before
    ``esa_cci.remove_xcube_cci_odp_attributes``, which removes the
    attribute.
    """

    suffix = "remove_xcube_cci_odp_dimensions"
    name = "Remove xcube-cci Open Data Portal dimensions"
    description = (
        "Removes the dimensions configured with the dimensions option, a "
        "list of dimension names, from the variables to which the xcube-cci "
        "Open Data Portal store adds them, by selecting the first index "
        "along them. The store repeats the values along dimensions that the "
        "original files do not have, such as the time dimension of 2-D "
        "latitudes and longitudes, and the longitude dimension of zonal "
        "means. Some datasets store each time step in a file without a time "
        "dimension, so only the configured dimensions are removed. The "
        "dimensions of the original files are read from the file_dimensions "
        "attribute that the store adds, so this must run before "
        "esa_cci.remove_xcube_cci_odp_attributes."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = RemoveXcubeCciOdpDimensionsOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[Hashable]]:
        dimensions: list[Hashable] = list(self.options.dimensions or [])
        wrong: dict[Hashable, list[Hashable]] = {}
        for name, variable in dataset.variables.items():
            if FILE_DIMENSIONS not in variable.attrs:
                continue
            file_dimensions = variable.attrs[FILE_DIMENSIONS]
            # netCDF stores a list with one item as a string.
            if isinstance(file_dimensions, str):
                file_dimensions = [file_dimensions]
            file_dimensions = [
                DIMENSION_NAMES.get(dim, dim) for dim in file_dimensions
            ]
            if added := [
                dim
                for dim in variable.dims
                if dim in dimensions and dim not in file_dimensions
            ]:
                wrong[name] = added
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            (
                f"{name} has dimensions {', '.join(map(str, added))}, which "
                "it does not have in the original files"
            )
            for name, added in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name, added in wrong.items():
                variable = dataset.variables[name]
                dataset[name] = variable.isel(dict.fromkeys(added, 0))
        return bool(wrong)
