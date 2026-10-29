"""Add scalar coordinates to ESA CCI datasets."""

from __future__ import annotations

import copy
from typing import Annotated

import numpy as np
import xarray as xr
from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options

from .set_attributes import Attributes, _equal


class ScalarCoordinate(Options):
    """The value and attributes of a scalar coordinate."""

    value: float | str
    attributes: Attributes


class AddScalarCoordinateOptions(Options):
    """Options of :class:`AddScalarCoordinate`."""

    coordinates: (
        Annotated[dict[str, ScalarCoordinate], Field(min_length=1)] | None
    ) = None


def _expected(coordinate: ScalarCoordinate) -> xr.Variable:
    """Return the scalar coordinate variable of ``coordinate``."""
    # Copy, so datasets do not share lists or dicts with the recipe options.
    attrs = copy.deepcopy(coordinate.attributes)
    if isinstance(coordinate.value, str):
        # Stored as a character array, like CMOR does, because not all
        # software reads netCDF-4 strings.
        return xr.Variable(
            (),
            np.str_(coordinate.value),
            attrs=attrs,
            encoding={"dtype": "S1"},
        )
    return xr.Variable((), np.float64(coordinate.value), attrs=attrs)


def _format(variable: xr.Variable) -> str:
    """Return the value of the scalar coordinate ``variable`` as text."""
    value = variable.to_numpy()[()]
    if isinstance(value, str):
        return repr(str(value))
    return f"{value:g}"


@register_fix_function
class AddScalarCoordinate(ConfigurableFix[AddScalarCoordinateOptions]):
    """Add scalar coordinates where they are missing or wrong.

    The coordinates are configured with the ``coordinates`` option, a
    mapping from coordinate name to its ``value`` and ``attributes``. A
    numeric coordinate is stored in double precision, and a string
    coordinate as a character array. A variable with the same name
    that is not a scalar coordinate raises an error.
    """

    suffix = "add_scalar_coordinate"
    name = "Add scalar coordinate"
    description = (
        "Adds the scalar coordinates configured with the coordinates option, "
        "a mapping from coordinate name to its value and attributes, when "
        "they are missing or have another value or attributes. The value "
        "is a number or a string. CMIP7 describes some variables with a "
        "scalar coordinate, e.g. the wavelength of 550 nm of the aerosol "
        "optical depth od550aer, which the ESA CCI datasets only give in "
        "the variable name, or the ocean surface layer of the surface "
        "chlorophyll concentration chl, a string coordinate."
    )
    categories = ["coordinates"]  # noqa: RUF012
    priority = 50
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = AddScalarCoordinateOptions

    def _wrong(self, dataset: xr.Dataset) -> dict[str, xr.Variable]:
        wrong = {}
        for name, coordinate in (self.options.coordinates or {}).items():
            expected = _expected(coordinate)
            if name not in dataset.variables:
                wrong[name] = expected
                continue
            current = dataset[name].variable
            if name not in dataset.coords or current.dims:
                msg = (
                    f"Unable to add scalar coordinate {name}: a variable "
                    "with that name exists"
                )
                raise ValueError(msg)
            if (
                current.dtype != expected.dtype
                or not _equal(current.to_numpy(), expected.to_numpy())
                or any(
                    not _equal(current.attrs.get(key), value)
                    for key, value in expected.attrs.items()
                )
            ):
                wrong[name] = expected
        return wrong

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._wrong(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        return [
            f"{name} is missing or differs from the expected scalar "
            f"coordinate with value {_format(variable)}"
            for name, variable in self._wrong(dataset).items()
        ]

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        wrong = self._wrong(dataset)
        if not dry_run:
            for name, variable in wrong.items():
                if name in dataset.variables:
                    variable.attrs = {
                        **dataset[name].attrs,
                        **variable.attrs,
                    }
                dataset.coords[name] = variable
        return bool(wrong)
