"""Validate the recipe options of fix functions."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Generic, Self, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field
from woodpecker.fixes.registry import FixFunction

# A non-empty list of names, e.g. of variables or attributes.
NonEmptyNames = Annotated[list[str], Field(min_length=1)]


class Options(BaseModel):
    """Base class for the recipe options of a fix function.

    Unknown options raise an error, so typos in recipes are not ignored.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


OptionsT = TypeVar("OptionsT", bound=Options)


class ConfigurableFix(FixFunction, Generic[OptionsT]):
    """Fix function with recipe options validated by ``options_model``.

    The validated options are available as ``options``. Woodpecker only
    calls ``configure`` for fixes with options, so the defaults of
    ``options_model`` are used for fixes without options.
    """

    options_model: ClassVar[type[Options]]
    options: OptionsT

    def __init__(self) -> None:
        super().__init__()
        self.options = cast("OptionsT", self.options_model())

    def configure(self, config: dict[str, Any] | None = None) -> Self:
        """Validate and store the recipe options in ``config``."""
        super().configure(config)
        options = self.options_model.model_validate(self.config)
        self.options = cast("OptionsT", options)
        return self
