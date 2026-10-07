"""Remove the packing encoding from all ESA CCI variables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# Encoding keys that describe how the values of a variable are packed. They
# become invalid when the values change. Without ``_FillValue``, an integer
# ``dtype`` writes missing values as valid numbers, so they are removed
# together.
PACKING_KEYS = (
    "_FillValue",
    "_Unsigned",
    "add_offset",
    "dtype",
    "missing_value",
    "scale_factor",
)


def _is_decoded_time(variable: xr.Variable) -> bool:
    """Return whether ``variable`` contains decoded times or durations."""
    # xarray moves the units of times and durations to the encoding when it
    # decodes them, and they define how the values are written.
    return "units" in variable.encoding


@register_fix_function
class RemovePacking(ConfigurableFix[Options]):
    """Remove the packing encoding from all variables, except decoded times.

    The packing encoding keys ``dtype``, ``scale_factor``, ``add_offset``,
    ``_FillValue``, ``missing_value`` and ``_Unsigned`` are removed from all
    data variables and coordinates that have them, except variables with
    decoded times or durations: their encoding defines the units and
    calendar the values are written in, see ``esa_cci.set_time_units``.

    xarray keeps the packing encoding when values change through
    ``copy(data=...)`` or in place, and then writes values that no longer
    fit, so packing is best added when writing.
    """

    suffix = "remove_packing"
    name = "Remove packing"
    description = (
        "Removes the packing encoding from all variables, except variables "
        "with decoded times."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = Options

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[str]]:
        wrong = {}
        for name, variable in dataset.variables.items():
            if _is_decoded_time(variable):
                continue
            if found := [
                key for key in PACKING_KEYS if key in variable.encoding
            ]:
                wrong[name] = found
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{name} has encoding {', '.join(keys)}"
            for name, keys in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name, keys in wrong.items():
                encoding = dataset.variables[name].encoding
                for key in keys:
                    del encoding[key]
        return bool(wrong)
