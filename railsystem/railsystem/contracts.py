"""Minimal, fail-closed domain contracts (simulation only)."""
from dataclasses import dataclass
from enum import Enum

class AuthorityStatus(Enum):
    UNKNOWN = "unknown"
    DENIED = "denied"
    GRANTED = "granted"

@dataclass(frozen=True)
class MovementAuthority:
    train_id: str
    status: AuthorityStatus
    issuer: str = ""

    def __post_init__(self):
        if not self.train_id:
            raise ValueError("train_id required")
        if not isinstance(self.status, AuthorityStatus):
            raise TypeError("status must be AuthorityStatus")

    @property
    def simulation_permitted(self) -> bool:
        return self.status is AuthorityStatus.GRANTED and bool(self.issuer)
