"""Remove encoding from all ESA CCI variables, except decoded times."""

from __future__ import annotations

from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from ._options import ConfigurableFix, NonEmptyNames, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr


def _is_decoded_time(variable: xr.Variable) -> bool:
    """Return whether ``variable`` contains decoded times or durations."""
    # xarray moves the units of times and durations to the encoding when it
    # decodes them, and they define how the values are written.
    return "units" in variable.encoding


class RemoveEncodingOptions(Options):
    """Options of :class:`RemoveEncoding`."""

    keys: NonEmptyNames | None = None


@register_fix_function
class RemoveEncoding(ConfigurableFix[RemoveEncodingOptions]):
    """Remove encoding keys from all variables, except decoded times.

    The keys are configured with the ``keys`` option, a list of encoding
    keys. They are removed from all data variables and coordinates that
    have them, except variables with decoded times or durations: their
    encoding defines the units and calendar the values are written in, see
    ``esa_cci.set_time_units``.

    Use this to remove the packing encoding: ``dtype``, ``scale_factor``,
    ``add_offset``, ``_FillValue``, ``missing_value`` and ``_Unsigned``.
    xarray keeps it when values change through ``copy(data=...)`` or in
    place, and then writes values that no longer fit, so packing is best
    added when writing. Remove these keys together: without ``_FillValue``,
    an integer ``dtype`` writes missing values as valid numbers.
    """

    suffix = "remove_encoding"
    name = "Remove encoding"
    description = (
        "Removes the configured encoding keys from all variables, except "
        "variables with decoded times."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = RemoveEncodingOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[str]]:
        keys = self.options.keys or []
        wrong = {}
        for name, variable in dataset.variables.items():
            if _is_decoded_time(variable):
                continue
            if found := [key for key in keys if key in variable.encoding]:
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
