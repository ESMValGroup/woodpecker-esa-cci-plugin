"""Remove references to coordinates that do not exist in ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# Where variables list their auxiliary coordinates. xarray moves the
# attribute to the encoding when it decodes a dataset, and writes it from
# there.
COORDINATES = "coordinates"


def _invalid(
    dataset: xr.Dataset, variable: xr.Variable
) -> dict[str, list[str]]:
    """Return the names in ``variable`` that are not in ``dataset``."""
    invalid = {}
    for where, mapping in (
        ("attribute", variable.attrs),
        ("encoding", variable.encoding),
    ):
        names = str(mapping.get(COORDINATES, "")).split()
        if missing := [
            name for name in names if name not in dataset.variables
        ]:
            invalid[where] = missing
    return invalid


@register_fix_function
class RemoveInvalidCoordinates(ConfigurableFix[Options]):
    """Remove the coordinates that do not exist from all variables.

    Names in the ``coordinates`` attribute, or in the ``coordinates``
    encoding of variables decoded by xarray, that are not variables of the
    dataset are removed. When no names are left, the attribute or encoding
    is removed, and xarray lists the coordinates of the variable when it
    writes the dataset.
    """

    suffix = "remove_invalid_coordinates"
    name = "Remove invalid coordinates"
    description = (
        "Removes the names of variables that do not exist from the "
        "coordinates attribute of all variables, or from where xarray keeps "
        "it after decoding, and removes the attribute when no names are left, "
        "so that xarray writes the coordinates that exist. Some ESA CCI "
        "datasets in the Open Data Portal store refer to coordinates named "
        "latitude and longitude, while the coordinates are named lat and lon."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = Options

    def _wrong(
        self, dataset: xr.Dataset
    ) -> dict[Hashable, dict[str, list[str]]]:
        wrong = {}
        for name, variable in dataset.variables.items():
            if invalid := _invalid(dataset, variable):
                wrong[name] = invalid
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{name} refers to coordinates {', '.join(missing)} in its "
            f"coordinates {where}, which do not exist"
            for name, invalid in self._wrong(dataset).items()
            for where, missing in invalid.items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name, invalid in wrong.items():
                variable = dataset.variables[name]
                for where, missing in invalid.items():
                    mapping = (
                        variable.attrs
                        if where == "attribute"
                        else variable.encoding
                    )
                    names = [
                        coordinate
                        for coordinate in str(mapping[COORDINATES]).split()
                        if coordinate not in missing
                    ]
                    if names:
                        mapping[COORDINATES] = " ".join(names)
                    else:
                        del mapping[COORDINATES]
        return bool(wrong)
