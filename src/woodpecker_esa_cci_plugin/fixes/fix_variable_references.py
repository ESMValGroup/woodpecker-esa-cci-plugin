"""Fix the references between variables of ESA CCI datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field
from woodpecker.fixes.labels import Labels
from woodpecker.fixes.registry import register_fix_function

from woodpecker_esa_cci_plugin.configurable_fix import ConfigurableFix, Options
from woodpecker_esa_cci_plugin.references import (
    REFERENCE_ATTRIBUTES,
    item_names,
    items,
    referenced_names,
)

if TYPE_CHECKING:
    from collections.abc import Hashable, MutableMapping

    import xarray as xr

# The reference attributes that can be configured. xarray manages the
# coordinates attribute itself, from the coordinates of the variables.
ConfigurableAttribute = Literal[
    "ancillary_variables",
    "bounds",
    "cell_measures",
    "climatology",
    "formula_terms",
    "grid_mapping",
]


class FixVariableReferencesOptions(Options):
    """Options of :class:`FixVariableReferences`."""

    references: (
        Annotated[
            dict[
                str,
                Annotated[
                    dict[ConfigurableAttribute, str], Field(min_length=1)
                ],
            ],
            Field(min_length=1),
        ]
        | None
    ) = None


def _mappings(
    variable: xr.Variable,
) -> tuple[tuple[str, MutableMapping[str, object]], ...]:
    """Return where ``variable`` keeps its reference attributes.

    xarray moves the coordinates attribute to the encoding when it decodes
    a dataset, and writes it from there.
    """
    return (("attribute", variable.attrs), ("encoding", variable.encoding))


def _valid_value(
    dataset: xr.Dataset, attribute: str, value: object
) -> str | None:
    """Return ``value`` without the items that refer to missing variables.

    Return ``None`` when no items are left.
    """
    valid = [
        " ".join(item)
        for item in items(attribute, value)
        if all(
            name in dataset.variables for name in item_names(attribute, item)
        )
    ]
    return " ".join(valid) if valid else None


@register_fix_function
class FixVariableReferences(ConfigurableFix[FixVariableReferencesOptions]):
    """Set the references between variables, and remove invalid ones.

    The references are configured with the ``references`` option, a
    mapping from variable name to a mapping of CF reference attributes,
    such as ``ancillary_variables`` and ``grid_mapping``, to their values.
    An empty value removes the attribute. Variables that do not exist, and
    references to them, raise an error.
    In the other reference attributes of all variables, the names of
    variables that do not exist are removed, and the attribute is removed
    when no names are left.
    """

    suffix = "fix_variable_references"
    name = "Fix variable references"
    description = (
        "Sets the CF attributes with which variables refer to other "
        "variables, such as ancillary_variables and grid_mapping, configured "
        "with the references option, a mapping from variable name to a "
        "mapping of attribute names to values, where an empty value removes "
        "the attribute. Removes the names of "
        "variables that do not exist from these attributes of all variables, "
        "and from the coordinates attribute or where xarray keeps it after "
        "decoding, and removes the attributes when no names are left. Run it "
        "before esa_cci.select_variables, which keeps the variables that the "
        "selected variables refer to, so that the variables that are not "
        "needed are dropped first and the other steps do not process them. "
        "Some ESA CCI datasets in the Open Data Portal store refer to "
        "coordinates named latitude and longitude, while the coordinates are "
        "named lat and lon."
    )
    categories = ["metadata"]  # noqa: RUF012
    # Run before select_variables, which keeps the referenced variables.
    priority = 55
    dataset = "ESA-CCI"
    labels = [Labels.RISK_METADATA_ONLY]  # noqa: RUF012
    options_model = FixVariableReferencesOptions

    def _configured(self, dataset: xr.Dataset) -> dict[str, dict[str, str]]:
        """Return the configured references that are not set yet."""
        wrong: dict[str, dict[str, str]] = {}
        for var, configured in (self.options.references or {}).items():
            references = {str(key): value for key, value in configured.items()}
            if var not in dataset.variables:
                msg = (
                    f"Unable to set the references of {var}: it does not exist"
                )
                raise ValueError(msg)
            if missing := [
                name
                for name in referenced_names(references)
                if name not in dataset.variables
            ]:
                msg = (
                    f"Unable to set the references of {var}: "
                    f"{', '.join(missing)} do not exist"
                )
                raise ValueError(msg)
            attrs = dataset[var].attrs
            if changes := {
                attribute: value
                for attribute, value in references.items()
                if attrs.get(attribute, "") != value
            }:
                wrong[var] = changes
        return wrong

    def _invalid(
        self, dataset: xr.Dataset
    ) -> dict[tuple[Hashable, str, str], tuple[list[str], str | None]]:
        """Return the reference attributes that refer to missing variables.

        The keys are the variable name, where the attribute is kept, and the
        attribute name. The values are the missing variables, and the value
        of the attribute without them.
        """
        references = self.options.references or {}
        invalid = {}
        for name, variable in dataset.variables.items():
            configured = references.get(str(name), {})
            for where, mapping in _mappings(variable):
                for attribute in REFERENCE_ATTRIBUTES:
                    if attribute not in mapping or (
                        where == "attribute" and attribute in configured
                    ):
                        continue
                    value = mapping[attribute]
                    if missing := [
                        ref
                        for ref in referenced_names({attribute: value})
                        if ref not in dataset.variables
                    ]:
                        invalid[name, where, attribute] = (
                            missing,
                            _valid_value(dataset, attribute, value),
                        )
        return invalid

    def matches(self, dataset: xr.Dataset) -> bool:
        """Return whether the fix applies to ``dataset``."""
        return bool(self._configured(dataset) or self._invalid(dataset))

    def check(self, dataset: xr.Dataset, **_options: object) -> list[str]:
        """Return a finding message for each detected problem."""
        messages = [
            f"{var} has {attribute} {dataset[var].attrs.get(attribute)!r}, "
            f"expected {value!r}"
            for var, changes in self._configured(dataset).items()
            for attribute, value in changes.items()
        ]
        messages.extend(
            f"{name} refers to {', '.join(missing)} in its {attribute} "
            f"{where}, which do not exist"
            for (name, where, attribute), (missing, _) in self._invalid(
                dataset
            ).items()
        )
        return messages

    def apply(
        self,
        dataset: xr.Dataset,
        dry_run: bool = True,  # noqa: FBT001, FBT002
    ) -> bool:
        """Apply the fix in place and return whether anything changed."""
        configured = self._configured(dataset)
        invalid = self._invalid(dataset)
        if not dry_run:
            for var, changes in configured.items():
                attrs = dataset[var].attrs
                for attribute, value in changes.items():
                    if value:
                        attrs[attribute] = value
                    else:
                        del attrs[attribute]
            for (name, where, attribute), (_, valid) in invalid.items():
                mapping = dict(_mappings(dataset.variables[name]))[where]
                if valid is None:
                    del mapping[attribute]
                else:
                    mapping[attribute] = valid
        return bool(configured or invalid)
