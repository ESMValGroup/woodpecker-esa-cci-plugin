"""Read the CF attributes with which variables refer to other variables."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

# CF attributes that contain a space separated list of variable names.
LIST_ATTRIBUTES = (
    "ancillary_variables",
    "bounds",
    "climatology",
    "coordinates",
    "geometry",
    "interior_ring",
    "node_coordinates",
    "node_count",
    "part_node_count",
)
# CF attributes that contain a list of "key: variable" pairs. The extended
# form of grid_mapping, "variable: coordinate ...", has grid mapping
# variables as keys, followed by the coordinates they apply to.
KEY_VALUE_ATTRIBUTES = ("cell_measures", "formula_terms", "grid_mapping")
REFERENCE_ATTRIBUTES = LIST_ATTRIBUTES + KEY_VALUE_ATTRIBUTES


def items(attribute: str, value: object) -> list[list[str]]:
    """Split the value of a reference attribute into items.

    An item is a list of the words that belong together, such as a single
    variable name or a key with its variables, so that removing an item
    keeps the value valid.
    """
    words = str(value).split()
    if attribute in LIST_ATTRIBUTES:
        return [[word] for word in words]
    grouped: list[list[str]] = []
    for word in words:
        if word.endswith(":") or not grouped:
            grouped.append([word])
        else:
            grouped[-1].append(word)
    return grouped


def item_names(attribute: str, item: list[str]) -> list[str]:
    """Return the names of the variables that ``item`` refers to."""
    if attribute == "grid_mapping":
        return [word.removesuffix(":") for word in item]
    return [word for word in item if not word.endswith(":")]


def referenced_names(attrs: Mapping[str, object]) -> Iterator[str]:
    """Yield the names of the variables that ``attrs`` refer to."""
    for attribute in REFERENCE_ATTRIBUTES:
        if attribute in attrs:
            for item in items(attribute, attrs[attribute]):
                yield from item_names(attribute, item)
