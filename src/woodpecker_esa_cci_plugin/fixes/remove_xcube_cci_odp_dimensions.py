"""Remove the dimensions that the xcube-cci Open Data Portal store adds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# The attribute in which the xcube-cci Open Data Portal store lists the
# dimensions of a variable in the original files.
FILE_DIMENSIONS = "file_dimensions"


@register_fix_function
class RemoveXcubeCciOdpDimensions(ConfigurableFix[Options]):
    """Remove the dimensions that the Open Data Portal store adds.

    The xcube-cci Open Data Portal store opens a netCDF file for each time
    step and stacks the variables along time, also the variables that the
    files store without a time dimension, such as 2-D latitudes and
    longitudes. Variables with dimensions that are not in their
    ``file_dimensions`` attribute are replaced by their first index along
    those dimensions, because the files repeat the same values. Datasets
    from other stores do not have the attribute, so the fix does nothing for
    those. It must run before ``esa_cci.remove_xcube_cci_odp_attributes``,
    which removes the attribute.
    """

    suffix = "remove_xcube_cci_odp_dimensions"
    name = "Remove xcube-cci Open Data Portal dimensions"
    description = (
        "Removes the dimensions that the xcube-cci Open Data Portal store "
        "adds to variables that the original files store without them, such "
        "as the time dimension of 2-D latitudes and longitudes, by selecting "
        "the first index along them. The dimensions of the original files "
        "are read from the file_dimensions attribute that the store adds, so "
        "this must run before esa_cci.remove_xcube_cci_odp_attributes."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_COORDINATE_TRANSFORMATION]  # noqa: RUF012
    options_model = Options

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[Hashable]]:
        wrong: dict[Hashable, list[Hashable]] = {}
        for name, variable in dataset.variables.items():
            if FILE_DIMENSIONS not in variable.attrs:
                continue
            file_dimensions = variable.attrs[FILE_DIMENSIONS]
            # netCDF stores a list with one item as a string.
            if isinstance(file_dimensions, str):
                file_dimensions = [file_dimensions]
            if added := [
                dim for dim in variable.dims if dim not in file_dimensions
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
