"""Explicit currency metadata registry for the ledger prototype.

This is an application-configured allowlist, not a claim to be a complete or
live ISO 4217 database. Production deployments must source and review metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .models import LedgerError

_CODE_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class CurrencySpec:
    code: str
    minor_unit_exponent: int
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not _CODE_RE.fullmatch(self.code):
            raise LedgerError("currency code must be three uppercase letters")
        if isinstance(self.minor_unit_exponent, bool) or not isinstance(self.minor_unit_exponent, int):
            raise LedgerError("minor_unit_exponent must be an integer")
        if not 0 <= self.minor_unit_exponent <= 6:
            raise LedgerError("minor_unit_exponent must be between 0 and 6")
        if not isinstance(self.enabled, bool):
            raise LedgerError("enabled must be bool")


class CurrencyRegistry:
    """Immutable explicit allowlist of currency codes and minor-unit scales."""

    def __init__(self, specs: Iterable[CurrencySpec]) -> None:
        items = tuple(specs)
        if any(not isinstance(spec, CurrencySpec) for spec in items):
            raise LedgerError("registry items must be CurrencySpec values")
        by_code: dict[str, CurrencySpec] = {}
        for spec in items:
            if spec.code in by_code:
                raise LedgerError(f"duplicate currency code {spec.code}")
            by_code[spec.code] = spec
        self._specs = by_code

    def get(self, code: str, *, require_enabled: bool = True) -> CurrencySpec:
        spec = self._specs.get(code)
        if spec is None:
            raise LedgerError(f"currency {code!r} is not registered")
        if require_enabled and not spec.enabled:
            raise LedgerError(f"currency {code!r} is disabled")
        return spec

    def codes(self, *, enabled_only: bool = True) -> tuple[str, ...]:
        return tuple(sorted(
            code for code, spec in self._specs.items()
            if spec.enabled or not enabled_only
        ))

    def to_dict(self) -> dict[str, dict[str, object]]:
        return {
            code: {"minor_unit_exponent": spec.minor_unit_exponent, "enabled": spec.enabled}
            for code, spec in sorted(self._specs.items())
        }
