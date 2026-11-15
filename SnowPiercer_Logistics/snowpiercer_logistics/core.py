"""Transactional, deterministic local cargo ledger; no physical actuation."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import hashlib
import json
import sqlite3
import threading

class AuthorizationError(PermissionError): pass
class ConflictError(ValueError): pass
class InvariantError(RuntimeError): pass

class CargoState(str, Enum):
    REGISTERED = "REGISTERED"
    STORED = "STORED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class MissionState(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

TRANSITIONS = {
    CargoState.REGISTERED: {CargoState.STORED, CargoState.CANCELLED},
    CargoState.STORED: {CargoState.IN_TRANSIT, CargoState.CANCELLED},
    CargoState.IN_TRANSIT: {CargoState.DELIVERED, CargoState.STORED},
    CargoState.DELIVERED: set(), CargoState.CANCELLED: set(),
}
MISSION_TRANSITIONS = {
    MissionState.PLANNED: {MissionState.ACTIVE, MissionState.CANCELLED},
    MissionState.ACTIVE: {MissionState.COMPLETED, MissionState.CANCELLED},
    MissionState.COMPLETED: set(), MissionState.CANCELLED: set(),
}

@dataclass(frozen=True)
class Principal:
    identity: str
    role: str

@dataclass(frozen=True)
class Cargo:
    cargo_id: str
    container_id: str
    location_id: str
    state: CargoState = CargoState.REGISTERED

@dataclass(frozen=True)
class Container:
    container_id: str
    capacity_kg: int

@dataclass(frozen=True)
class Location:
    location_id: str
    kind: str

@dataclass(frozen=True)
class Transfer:
    transfer_id: str
    cargo_id: str
    source: str
    destination: str

@dataclass(frozen=True)
class Mission:
    mission_id: str
    cargo_id: str
    state: MissionState = MissionState.PLANNED

class LogisticsLedger:
    """SQLite WAL ledger; one transaction per command; callers supply trusted principals.

    Explicitly NOT an OS-backed identity or tamper-proof ledger.
    """
    def __init__(self, path):
        self.path = str(Path(path))
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, isolation_level=None, timeout=10, check_same_thread=False)
        self._closed = False
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS containers(id TEXT PRIMARY KEY, capacity_kg INTEGER NOT NULL CHECK(capacity_kg > 0));
        CREATE TABLE IF NOT EXISTS locations(id TEXT PRIMARY KEY, kind TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cargo(id TEXT PRIMARY KEY, container_id TEXT NOT NULL REFERENCES containers(id), location_id TEXT NOT NULL REFERENCES locations(id), state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, cargo_id TEXT NOT NULL REFERENCES cargo(id), state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transfers(id TEXT PRIMARY KEY, cargo_id TEXT NOT NULL REFERENCES cargo(id), source TEXT NOT NULL, destination TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commands(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, command_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
        """)

    def close(self):
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True

    def __del__(self):
        if not getattr(self, "_closed", True):
            import warnings
            warnings.warn("LogisticsLedger requires explicit close()", ResourceWarning)
            self.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    @staticmethod
    def _required(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("Identifier must be a nonempty string of at most 256 characters")

    @staticmethod
    def _authorize(principal, action):
        if not isinstance(principal, Principal) or not principal.identity:
            raise AuthorizationError("Missing trusted principal")
        permissions = {"admin": {"setup", "write", "read"}, "operator": {"write", "read"}, "auditor": {"read"}}
        if action not in permissions.get(principal.role, set()):
            raise AuthorizationError("Permission denied")

    def _command(self, principal, action, key, kind, payload, apply):
        self._authorize(principal, action)
        self._required(key)
        canonical = json.dumps({"kind": kind, "payload": payload, "principal": principal.identity}, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._admit_command(self._db, principal, key, kind, payload)
                previous = self._db.execute("SELECT fingerprint,result FROM commands WHERE key=?", (key,)).fetchone()
                if previous:
                    if previous[0] != fingerprint: raise ConflictError("Idempotency key reused with different command")
                    result = json.loads(previous[1])
                else:
                    result = apply(self._db)
                    result_text = json.dumps(result, sort_keys=True, separators=(",", ":"))
                    last = self._db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
                    prev_hash = last[0] if last else "0" * 64
                    event_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                    event_hash = hashlib.sha256((prev_hash + key + kind + event_payload).encode()).hexdigest()
                    self._db.execute("INSERT INTO events(command_key,kind,payload,previous_hash,event_hash) VALUES(?,?,?,?,?)", (key, kind, event_payload, prev_hash, event_hash))
                    self._db.execute("INSERT INTO commands(key,fingerprint,result) VALUES(?,?,?)", (key, fingerprint, result_text))
                self._db.execute("COMMIT")
                return result
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def _admit_command(self, db, principal, key, kind, payload):
        """Optional policy hook, inside the same write transaction as the effect.

        The original ledger has no additional admission policy. Subclasses must
        raise before mutation when their integration preconditions are unmet.
        """
        return None

    def add_container(self, principal, key, container: Container):
        self._required(container.container_id)
        if type(container.capacity_kg) is not int or container.capacity_kg <= 0: raise ValueError("Invalid capacity")
        def apply(db):
            db.execute("INSERT INTO containers VALUES(?,?)", (container.container_id, container.capacity_kg))
            return {"container_id": container.container_id}
        return self._command(principal, "setup", key, "container.add", vars(container), apply)

    def add_location(self, principal, key, location: Location):
        self._required(location.location_id)
        self._required(location.kind)
        def apply(db):
            db.execute("INSERT INTO locations VALUES(?,?)", (location.location_id, location.kind))
            return {"location_id": location.location_id}
        return self._command(principal, "setup", key, "location.add", vars(location), apply)

    def register_cargo(self, principal, key, cargo: Cargo):
        for value in (cargo.cargo_id, cargo.container_id, cargo.location_id): self._required(value)
        if cargo.state != CargoState.REGISTERED: raise ValueError("Cargo must begin REGISTERED")
        def apply(db):
            db.execute("INSERT INTO cargo VALUES(?,?,?,?)", (cargo.cargo_id, cargo.container_id, cargo.location_id, cargo.state.value))
            return {"cargo_id": cargo.cargo_id, "state": cargo.state.value}
        return self._command(principal, "write", key, "cargo.register", {"cargo_id":cargo.cargo_id,"container_id":cargo.container_id,"location_id":cargo.location_id,"state":cargo.state.value}, apply)

    def transition_cargo(self, principal, key, cargo_id, target: CargoState):
        self._required(cargo_id)
        target = CargoState(target)
        def apply(db):
            row = db.execute("SELECT state FROM cargo WHERE id=?", (cargo_id,)).fetchone()
            if not row: raise ConflictError("Unknown cargo")
            source = CargoState(row[0])
            if target not in TRANSITIONS[source]: raise ConflictError("Forbidden cargo transition")
            db.execute("UPDATE cargo SET state=? WHERE id=?", (target.value, cargo_id))
            return {"cargo_id": cargo_id, "state": target.value}
        return self._command(principal, "write", key, "cargo.transition", {"cargo_id":cargo_id,"target":target.value}, apply)

    def create_mission(self, principal, key, mission: Mission):
        self._required(mission.mission_id)
        self._required(mission.cargo_id)
        if mission.state != MissionState.PLANNED: raise ValueError("Mission must begin PLANNED")
        def apply(db):
            db.execute("INSERT INTO missions VALUES(?,?,?)", (mission.mission_id, mission.cargo_id, mission.state.value))
            return {"mission_id":mission.mission_id,"state":mission.state.value}
        return self._command(principal, "write", key, "mission.create", {"mission_id":mission.mission_id,"cargo_id":mission.cargo_id}, apply)

    def transition_mission(self, principal, key, mission_id, target: MissionState):
        self._required(mission_id)
        target = MissionState(target)
        def apply(db):
            row = db.execute("SELECT state FROM missions WHERE id=?", (mission_id,)).fetchone()
            if not row: raise ConflictError("Unknown mission")
            if target not in MISSION_TRANSITIONS[MissionState(row[0])]: raise ConflictError("Forbidden mission transition")
            db.execute("UPDATE missions SET state=? WHERE id=?", (target.value, mission_id))
            return {"mission_id":mission_id,"state":target.value}
        return self._command(principal, "write", key, "mission.transition", {"mission_id":mission_id,"target":target.value}, apply)

    def record_transfer(self, principal, key, transfer: Transfer):
        for value in vars(transfer).values(): self._required(value)
        if transfer.source == transfer.destination: raise ConflictError("Transfer must change location")
        def apply(db):
            row = db.execute("SELECT location_id,state FROM cargo WHERE id=?", (transfer.cargo_id,)).fetchone()
            if not row or row != (transfer.source, CargoState.IN_TRANSIT.value): raise ConflictError("Cargo must be in transit at source")
            if not db.execute("SELECT 1 FROM locations WHERE id=?", (transfer.destination,)).fetchone(): raise ConflictError("Unknown destination")
            db.execute("INSERT INTO transfers VALUES(?,?,?,?)", (transfer.transfer_id, transfer.cargo_id, transfer.source, transfer.destination))
            db.execute("UPDATE cargo SET location_id=?,state=? WHERE id=?", (transfer.destination, CargoState.STORED.value, transfer.cargo_id))
            return {"transfer_id":transfer.transfer_id,"location_id":transfer.destination,"state":CargoState.STORED.value}
        return self._command(principal, "write", key, "cargo.transfer", vars(transfer), apply)

    def get_cargo(self, principal, cargo_id):
        self._authorize(principal, "read")
        with self._lock:
            row = self._db.execute("SELECT id,container_id,location_id,state FROM cargo WHERE id=?", (cargo_id,)).fetchone()
        return Cargo(row[0], row[1], row[2], CargoState(row[3])) if row else None

    def verify(self, principal):
        self._authorize(principal, "read")
        with self._lock:
            fk = self._db.execute("PRAGMA foreign_key_check").fetchall()
            if fk: raise InvariantError("Foreign key violation")
            integrity = self._db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok": raise InvariantError("SQLite integrity failure")
            events = self._db.execute("SELECT command_key,kind,payload,previous_hash,event_hash FROM events ORDER BY seq").fetchall()
            commands = self._db.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
            if commands != len(events): raise InvariantError("Command/event mismatch")
            previous = "0" * 64
            for key, kind, payload, prev_hash, event_hash in events:
                expected = hashlib.sha256((previous + key + kind + payload).encode()).hexdigest()
                if previous != prev_hash or expected != event_hash: raise InvariantError("Event hash chain broken")
                previous = event_hash
            for (state,) in self._db.execute("SELECT state FROM cargo"):
                if state not in CargoState._value2member_map_: raise InvariantError("Invalid cargo state")
            for (state,) in self._db.execute("SELECT state FROM missions"):
                if state not in MissionState._value2member_map_: raise InvariantError("Invalid mission state")
            return {"events":len(events),"head_hash":previous,"sqlite_integrity":"ok"}
