"""Typed reading of environment variables, with errors that name the variable.

A blank value counts as unset, so the default applies. A bad value raises
ConfigError with the variable name, the value and what was expected, so a wrong
setting is found from one line instead of a bare ValueError traceback.
"""

from __future__ import annotations

import math
import os
from collections.abc import Collection


class ConfigError(ValueError):
    """An environment variable holds a value that cannot be used."""


def _raw(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip() or None


def _check_range(
    name: str,
    value: int | float,
    minimum: int | float | None,
    maximum: int | float | None,
) -> None:
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name}={value} is below the minimum {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name}={value} is above the maximum {maximum}")


def env_int(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw = _raw(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a whole number") from None
    _check_range(name, value, minimum, maximum)
    return value


def env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw = _raw(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a number") from None
    if not math.isfinite(value):
        raise ConfigError(f"{name}={raw!r} is not a finite number")
    _check_range(name, value, minimum, maximum)
    return value


def env_choice(name: str, default: str, choices: Collection[str]) -> str:
    """Return the value lowercased; choices must be written in lowercase."""
    raw = _raw(name)
    if raw is None:
        return default
    value = raw.lower()
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ConfigError(f"{name}={raw!r} is not one of: {allowed}")
    return value
