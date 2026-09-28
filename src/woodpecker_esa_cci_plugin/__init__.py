"""Woodpecker plugin providing ESA CCI dataset fixes and recipes.

Importing this package registers its fixes with woodpecker. Woodpecker
imports it automatically through the ``woodpecker.plugins`` entry point.
"""

from .esa_cci_0001 import AddTcwvStandardName

__all__ = ["AddTcwvStandardName"]
