"""Woodpecker plugin providing ESA CCI dataset fixes and recipes.

Importing this package registers its fixes with woodpecker. Woodpecker
imports it automatically through the ``woodpecker.plugins`` entry point.
"""

from .convert_units import ConvertUnits
from .grid_mapping_from_wkt import GridMappingFromWkt
from .normalize_longitude import NormalizeLongitude
from .select_variables import SelectVariables
from .set_attributes import SetAttributes
from .set_time_units import SetTimeUnits

__all__ = [
    "ConvertUnits",
    "GridMappingFromWkt",
    "NormalizeLongitude",
    "SelectVariables",
    "SetAttributes",
    "SetTimeUnits",
]
