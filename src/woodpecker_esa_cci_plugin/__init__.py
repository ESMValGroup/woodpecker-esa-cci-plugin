"""Woodpecker plugin providing ESA CCI dataset fixes and recipes.

Importing this package registers its fixes with woodpecker. Woodpecker
imports it automatically through the ``woodpecker.plugins`` entry point.
"""

from .convert_units import ConvertUnits
from .grid_mapping_from_wkt import GridMappingFromWkt
from .normalize_longitude import NormalizeLongitude
from .remove_attributes import RemoveAttributes
from .remove_encoding import RemoveEncoding
from .select_variables import SelectVariables
from .set_attributes import SetAttributes
from .set_global_attributes import SetGlobalAttributes
from .set_time_units import SetTimeUnits

__all__ = [
    "ConvertUnits",
    "GridMappingFromWkt",
    "NormalizeLongitude",
    "RemoveAttributes",
    "RemoveEncoding",
    "SelectVariables",
    "SetAttributes",
    "SetGlobalAttributes",
    "SetTimeUnits",
]
