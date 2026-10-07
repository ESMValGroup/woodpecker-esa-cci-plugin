"""Woodpecker plugin providing ESA CCI dataset fixes and recipes.

Importing this package registers its fixes with woodpecker. Woodpecker
imports it automatically through the ``woodpecker.plugins`` entry point.
"""

from .fixes.add_bounds import AddBounds
from .fixes.center_monthly_time import CenterMonthlyTime
from .fixes.convert_units import ConvertUnits
from .fixes.grid_mapping_from_wkt import GridMappingFromWkt
from .fixes.normalize_longitude import NormalizeLongitude
from .fixes.remove_attributes import RemoveAttributes
from .fixes.remove_global_attributes import RemoveGlobalAttributes
from .fixes.remove_packing import RemovePacking
from .fixes.remove_range_attributes import RemoveRangeAttributes
from .fixes.select_variables import SelectVariables
from .fixes.set_attributes import SetAttributes
from .fixes.set_data_types import SetDataTypes
from .fixes.set_global_attributes import SetGlobalAttributes
from .fixes.set_time_units import SetTimeUnits

__all__ = [
    "AddBounds",
    "CenterMonthlyTime",
    "ConvertUnits",
    "GridMappingFromWkt",
    "NormalizeLongitude",
    "RemoveAttributes",
    "RemoveGlobalAttributes",
    "RemovePacking",
    "RemoveRangeAttributes",
    "SelectVariables",
    "SetAttributes",
    "SetDataTypes",
    "SetGlobalAttributes",
    "SetTimeUnits",
]
