"""Remove the attributes that the xcube-cci Open Data Portal store adds."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    from collections.abc import Hashable

    import xarray as xr

# Variable attributes that the xcube-cci Open Data Portal store adds to
# describe the variables in the original files. They are not part of the
# ESA CCI data and become invalid when the data changes, e.g. data_type and
# fill_value after removing the packing.
XCUBE_CCI_ATTRIBUTES = (
    "chunk_sizes",
    "data_type",
    "dimensions",
    "file_chunk_sizes",
    "file_dimensions",
    "fill_value",
    "orig_data_type",
    "shape",
    "size",
)
# The xcube-cci Open Data Portal store replaces the history global attribute
# with a list that describes how it opened the data. netCDF attributes cannot
# be lists of mappings, and CF requires a history string.
HISTORY = "history"


def history_string(history: object) -> str:
    """Return ``history`` as a string, with one line for each entry."""
    entries = history if isinstance(history, list) else [history]
    return "\n".join(json.dumps(entry, default=str) for entry in entries)


@register_fix_function
class RemoveXcubeCciAttributes(ConfigurableFix[Options]):
    """Remove the attributes that the xcube-cci Open Data Portal store adds.

    The attributes in ``XCUBE_CCI_ATTRIBUTES`` are removed from all
    variables that have them. A ``history`` global attribute that is not a
    string is converted to one, with each entry as JSON on its own line.
    Datasets from other stores do not have them, so the fix does nothing for
    those.
    """

    suffix = "remove_xcube_cci_attributes"
    name = "Remove xcube-cci attributes"
    description = (
        "Removes the attributes that the xcube-cci Open Data Portal store "
        "adds to describe the original files: chunk_sizes, data_type, "
        "dimensions, file_chunk_sizes, file_dimensions, fill_value, "
        "orig_data_type, shape and size from all variables. They become "
        "invalid when the data changes, and some are not valid netCDF "
        "attributes. It also converts the history global attribute, which "
        "the store sets to a list, to a string."
    )
    categories = ["metadata"]  # noqa: RUF012
    priority = 30
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = Options

    def _wrong(self, dataset: xr.Dataset) -> dict[Hashable, list[str]]:
        wrong: dict[Hashable, list[str]] = {}
        for name, variable in dataset.variables.items():
            if keys := [
                key for key in XCUBE_CCI_ATTRIBUTES if key in variable.attrs
            ]:
                wrong[name] = keys
        return wrong

    def _wrong_history(self, dataset: xr.Dataset) -> bool:
        return HISTORY in dataset.attrs and not isinstance(
            dataset.attrs[HISTORY], str
        )

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset)) or self._wrong_history(dataset)

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        messages = [
            f"{name} has attributes {', '.join(keys)}"
            for name, keys in self._wrong(dataset).items()
        ]
        if self._wrong_history(dataset):
            messages.append("the history global attribute is not a string")
        return messages

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        wrong_history = self._wrong_history(dataset)
        if not dry_run:
            for name, keys in wrong.items():
                attrs = dataset.variables[name].attrs
                for key in keys:
                    del attrs[key]
            if wrong_history:
                dataset.attrs[HISTORY] = history_string(dataset.attrs[HISTORY])
        return bool(wrong) or wrong_history
