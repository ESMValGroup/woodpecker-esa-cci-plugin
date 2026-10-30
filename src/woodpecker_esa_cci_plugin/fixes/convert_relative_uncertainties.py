"""Convert relative uncertainties of ESA CCI variables to absolute ones."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .convert_units import _convert as _convert_units
from .convert_units import _parse
from .remove_range_attributes import remove_range_attributes

if TYPE_CHECKING:
    import xarray as xr


class ConvertRelativeUncertaintiesOptions(Options):
    """Options of :class:`ConvertRelativeUncertainties`."""

    uncertainties: Annotated[dict[str, str], Field(min_length=1)] | None = None


@register_fix_function
class ConvertRelativeUncertainties(
    ConfigurableFix[ConvertRelativeUncertaintiesOptions]
):
    """Convert relative uncertainties to the units of their variable.

    The uncertainties are configured with the ``uncertainties`` option, a
    mapping from the name of a relative uncertainty, e.g. in percent, to the
    name of the variable it is relative to. Each uncertainty is multiplied
    by the variable and gets its units, so an uncertainty with the units of
    its variable has been converted. The range attributes of the
    uncertainties are removed. Variables that do not exist or have no units,
    and uncertainties with units that are not dimensionless, raise an error.
    """

    suffix = "convert_relative_uncertainties"
    name = "Convert relative uncertainties"
    description = (
        "Converts the relative uncertainties configured with the "
        "uncertainties option, a mapping from the name of an uncertainty to "
        "the name of the variable it is relative to, to absolute "
        "uncertainties, by multiplying them by the variable, and gives them "
        "its units. Some ESA CCI datasets store uncertainties in percent of "
        "the variable, while CF requires a standard error to have the units "
        "of its variable. The range attributes of the uncertainties are "
        "removed."
    )
    categories = ["data", "units"]  # noqa: RUF012
    # After esa_cci.convert_units, so they get the converted units.
    priority = 41
    dataset = "ESA-CCI"
    labels = [Labels.RISK_VALUE_TRANSFORMATION]  # noqa: RUF012
    options_model = ConvertRelativeUncertaintiesOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, str]:
        wrong = {}
        for uncertainty, var in (self.options.uncertainties or {}).items():
            action = f"Unable to convert {uncertainty} relative to {var}"
            for name in (uncertainty, var):
                if name not in dataset.variables:
                    msg = f"{action}: {name} does not exist"
                    raise ValueError(msg)
                if "units" not in dataset[name].attrs:
                    msg = f"{action}: {name} has no units"
                    raise ValueError(msg)
            units = dataset[uncertainty].attrs["units"]
            if units == dataset[var].attrs["units"]:
                continue
            if not _parse(units)[1].dimensionless:
                msg = f"{action}: its units {units!r} are not dimensionless"
                raise ValueError(msg)
            wrong[uncertainty] = var
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{uncertainty} is relative to {var}"
            for uncertainty, var in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for uncertainty, var in wrong.items():
                _convert(dataset, uncertainty, var)
        return bool(wrong)


def _convert(dataset: xr.Dataset, uncertainty: str, var: str) -> None:
    """Convert ``uncertainty`` relative to ``var`` in ``dataset``."""
    variable = dataset[uncertainty].variable
    # The fraction of the variable of one unit, e.g. 0.01 for percent.
    fraction = _convert_units(1, variable.attrs["units"], "1")
    absolute = variable * fraction * dataset[var].variable
    variable = variable.copy(data=absolute.transpose(*variable.dims).data)
    remove_range_attributes(variable)
    variable.attrs["units"] = dataset[var].attrs["units"]
    dataset[uncertainty] = variable
