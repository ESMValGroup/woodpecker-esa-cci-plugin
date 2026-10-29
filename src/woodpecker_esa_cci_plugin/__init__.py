"""Woodpecker plugin providing ESA CCI dataset fixes and recipes.

Importing this package registers its fixes with woodpecker. Woodpecker
imports it automatically through the ``woodpecker.plugins`` entry point.
"""

from .fixes.add_bounds import AddBounds
from .fixes.add_geographic_bounds import AddGeographicBounds
from .fixes.add_scalar_coordinate import AddScalarCoordinate
from .fixes.apply_valid_range import ApplyValidRange
from .fixes.center_time import CenterTime
from .fixes.convert_relative_uncertainties import (
    ConvertRelativeUncertainties,
)
from .fixes.convert_units import ConvertUnits
from .fixes.fill_time_gaps import FillTimeGaps
from .fixes.grid_mapping_from_wkt import GridMappingFromWkt
from .fixes.mask_flag_values import MaskFlagValues
from .fixes.normalize_longitude import NormalizeLongitude
from .fixes.remove_attributes import RemoveAttributes
from .fixes.remove_global_attributes import RemoveGlobalAttributes
from .fixes.remove_invalid_coordinates import RemoveInvalidCoordinates
from .fixes.remove_packing import RemovePacking
from .fixes.remove_range_attributes import RemoveRangeAttributes
from .fixes.remove_xcube_cci_odp_attributes import RemoveXcubeCciOdpAttributes
from .fixes.remove_xcube_cci_odp_dimensions import RemoveXcubeCciOdpDimensions
from .fixes.select_coordinate_values import SelectCoordinateValues
from .fixes.select_time_steps import SelectTimeSteps
from .fixes.select_variables import SelectVariables
from .fixes.set_attributes import SetAttributes
from .fixes.set_data_types import SetDataTypes
from .fixes.set_global_attributes import SetGlobalAttributes
from .fixes.set_time_units import SetTimeUnits

__all__ = [
    "AddBounds",
    "AddGeographicBounds",
    "AddScalarCoordinate",
    "ApplyValidRange",
    "CenterTime",
    "ConvertRelativeUncertainties",
    "ConvertUnits",
    "FillTimeGaps",
    "GridMappingFromWkt",
    "MaskFlagValues",
    "NormalizeLongitude",
    "RemoveAttributes",
    "RemoveGlobalAttributes",
    "RemoveInvalidCoordinates",
    "RemovePacking",
    "RemoveRangeAttributes",
    "RemoveXcubeCciOdpAttributes",
    "RemoveXcubeCciOdpDimensions",
    "SelectCoordinateValues",
    "SelectTimeSteps",
    "SelectVariables",
    "SetAttributes",
    "SetDataTypes",
    "SetGlobalAttributes",
    "SetTimeUnits",
]
