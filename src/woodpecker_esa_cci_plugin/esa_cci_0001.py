"""Add the CF standard_name to the ESA CCI water vapour variable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import FixFunction, register_fix_function

if TYPE_CHECKING:
    import xarray as xr

VARIABLE = "tcwv"
STANDARD_NAME = "atmosphere_mass_content_of_water_vapor"


def _needs_fix(dataset: xr.Dataset) -> bool:
    return VARIABLE in dataset.data_vars and not dataset[VARIABLE].attrs.get(
        "standard_name"
    )


@register_fix_function
class AddTcwvStandardName(FixFunction):
    """Set ``standard_name`` on ``tcwv`` when it is missing."""

    suffix = "add_tcwv_standard_name"
    name = "Add tcwv standard_name"
    description = (
        f"Sets standard_name to '{STANDARD_NAME}' on the {VARIABLE} "
        "variable when it is missing."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return _needs_fix(dataset)

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        if not _needs_fix(dataset):
            return []
        return [f"{VARIABLE} is missing standard_name"]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        if not _needs_fix(dataset):
            return False
        if not dry_run:
            dataset[VARIABLE].attrs["standard_name"] = STANDARD_NAME
        return True
