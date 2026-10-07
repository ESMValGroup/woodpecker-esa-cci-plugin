"""Set the data types of ESA CCI variables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import numpy as np
from pydantic import AfterValidator, Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

if TYPE_CHECKING:
    import xarray as xr


def _check_data_type(value: str) -> str:
    """Raise an error if ``value`` is not a numpy data type."""
    try:
        np.dtype(value)
    except TypeError as exc:
        msg = f"{value!r} is not a data type"
        raise ValueError(msg) from exc
    return value


DataType = Annotated[str, AfterValidator(_check_data_type)]


class SetDataTypesOptions(Options):
    """Options of :class:`SetDataTypes`."""

    data_types: Annotated[dict[str, DataType], Field(min_length=1)] | None = (
        None
    )


@register_fix_function
class SetDataTypes(ConfigurableFix[SetDataTypesOptions]):
    """Convert variables to the configured data types.

    The data types are configured with the ``data_types`` option, a mapping
    from variable name to a numpy data type, e.g. ``float32``. The values
    are converted, and the ``dtype`` encoding of the converted variables is
    removed, so they are written in the new data type. Variables that do
    not exist raise an error.
    """

    suffix = "set_data_types"
    name = "Set data types"
    description = (
        "Converts the variables configured with the data_types option, a "
        "mapping from variable name to a numpy data type such as float32, "
        "to that data type, and writes them in that data type."
    )
    categories = ["structure"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VALUE_TRANSFORMATION]  # noqa: RUF012
    options_model = SetDataTypesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, np.dtype]:
        wrong = {}
        for var, data_type in (self.options.data_types or {}).items():
            if var not in dataset.variables:
                msg = (
                    f"Unable to set the data type of {var}: it does not exist"
                )
                raise ValueError(msg)
            dtype = np.dtype(data_type)
            if dataset[var].dtype != dtype:
                wrong[var] = dtype
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{var} has data type {dataset[var].dtype}, expected {dtype}"
            for var, dtype in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for var, dtype in wrong.items():
                variable = dataset[var].variable.astype(dtype)
                # Otherwise xarray writes the values in the original type.
                variable.encoding.pop("dtype", None)
                # Assign to also update the index of dimension coordinates.
                dataset[var] = variable
        return bool(wrong)
