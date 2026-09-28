"""Turn a WKT coordinate reference system into a CF grid mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import CRS
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import FixFunction, register_fix_function

if TYPE_CHECKING:
    import xarray as xr


@register_fix_function
class GridMappingFromWkt(FixFunction):
    """Set CF grid mapping attributes from a WKT attribute.

    The grid mapping variable is configured with the ``variable`` option and
    the attribute that holds its WKT string with the ``wkt_attribute``
    option. The WKT attribute is replaced by the CF ``crs_wkt`` attribute.
    """

    suffix = "grid_mapping_from_wkt"
    name = "Grid mapping from WKT"
    description = (
        "Sets the CF grid mapping attributes of the configured variable from "
        "its WKT attribute and replaces that attribute with crs_wkt."
    )
    categories = ["metadata", "coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012

    def _option(self, name: str) -> str | None:
        value = self.config.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            msg = f"The {name} option must be a string"
            raise TypeError(msg)
        return value

    def _wkt(self, dataset: xr.Dataset) -> tuple[str, str] | None:
        """Return the variable and WKT attribute names if there is work."""
        variable = self._option("variable")
        wkt_attribute = self._option("wkt_attribute")
        if variable is None or wkt_attribute is None:
            return None
        if variable not in dataset.variables:
            return None
        if wkt_attribute not in dataset[variable].attrs:
            return None
        return variable, wkt_attribute

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return self._wkt(dataset) is not None

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if (found := self._wkt(dataset)) is None:
            return []
        variable, wkt_attribute = found
        return [
            (
                f"{variable} describes its CRS with the non-CF "
                f"{wkt_attribute} attribute"
            )
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if (found := self._wkt(dataset)) is None:
            return False
        if not dry_run:
            variable, wkt_attribute = found
            attrs = dataset[variable].attrs
            attrs.update(CRS.from_wkt(attrs.pop(wkt_attribute)).to_cf())
        return True
