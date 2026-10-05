"""Turn a WKT coordinate reference system into a CF grid mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import model_validator
from pyproj import CRS
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from ._options import ConfigurableFix, Options

if TYPE_CHECKING:
    import xarray as xr


class GridMappingFromWktOptions(Options):
    """Options of :class:`GridMappingFromWkt`."""

    variable: str | None = None
    wkt_attribute: str | None = None

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        if (self.variable is None) != (self.wkt_attribute is None):
            msg = "The variable and wkt_attribute options must both be set"
            raise ValueError(msg)
        return self


@register_fix_function
class GridMappingFromWkt(ConfigurableFix[GridMappingFromWktOptions]):
    """Set CF grid mapping attributes from a WKT attribute.

    The grid mapping variable is configured with the ``variable`` option and
    the attribute that holds its WKT string with the ``wkt_attribute``
    option. The WKT attribute is replaced by the CF ``crs_wkt`` attribute.
    A missing variable or WKT attribute raises an error.
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
    options_model = GridMappingFromWktOptions

    def _wkt(self, dataset: xr.Dataset) -> tuple[str, str] | None:
        """Return the variable and WKT attribute names if configured."""
        variable = self.options.variable
        wkt_attribute = self.options.wkt_attribute
        if variable is None or wkt_attribute is None:
            return None
        if variable not in dataset.variables:
            msg = f"Unable to read the WKT of {variable}: it does not exist"
            raise ValueError(msg)
        if wkt_attribute not in dataset[variable].attrs:
            msg = (
                f"Unable to read the WKT of {variable}: it has no "
                f"{wkt_attribute} attribute"
            )
            raise ValueError(msg)
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
            # Parse before removing the WKT attribute, so it is kept if
            # parsing fails.
            cf_attrs = CRS.from_wkt(attrs[wkt_attribute]).to_cf()
            del attrs[wkt_attribute]
            attrs.update(cf_attrs)
        return True
