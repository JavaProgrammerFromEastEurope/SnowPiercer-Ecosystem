"""Strict offline registry validation; no equipment control."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import json
import re

ID = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
AREAS = frozenset({"CORE","ATMOSPHERE","VENTILATION","THERMAL","HUMIDITY","WATER","WATER-RECOVERY","SANITATION","WASTE","FOOD","AGRICULTURE","MEDICAL","HABITAT","FIRE-SAFETY","SENSORS","CONTROL","RESILIENCE","RESOURCES","DIGITAL-TWIN","INTEGRATION"})
STATUSES = frozenset({"proposed", "specified", "verified", "retired"})

class RegistryError(ValueError):
    pass

def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{label} must be a nonempty string")
    return value

def _unique_ids(items: list[dict], kind: str) -> dict[str,dict]:
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise RegistryError(f"{kind} entry must be object")
        ident = _nonempty(item.get("id"), f"{kind}.id")
        if not ID.fullmatch(ident):
            raise RegistryError(f"invalid {kind} id: {ident}")
        if ident in result:
            raise RegistryError(f"duplicate {kind} id: {ident}")
        result[ident] = item
    return result

@dataclass(frozen=True)
class Registry:
    components: dict[str,dict]
    requirements: dict[str,dict]
    version: str

    @classmethod
    def from_dict(cls, data: dict) -> 'Registry':
        if not isinstance(data, dict) or data.get("schema_version") != "1.0":
            raise RegistryError("unsupported registry schema_version")
        components = _unique_ids(data.get("components", []), "component")
        requirements = _unique_ids(data.get("requirements", []), "requirement")
        if not components or not requirements:
            raise RegistryError("components and requirements must not be empty")
        for cid, c in components.items():
            _nonempty(c.get("name"), f"{cid}.name")
            if c.get("area") not in AREAS:
                raise RegistryError(f"{cid}: unknown area")
            if c.get("status") not in STATUSES:
                raise RegistryError(f"{cid}: unknown status")
            deps = c.get("depends_on")
            if not isinstance(deps, list) or any(not isinstance(x,str) for x in deps) or len(deps) != len(set(deps)):
                raise RegistryError(f"{cid}: invalid dependencies")
            for dep in deps:
                if dep not in components:
                    raise RegistryError(f"{cid}: unknown dependency {dep}")
                if dep == cid:
                    raise RegistryError(f"{cid}: self dependency")
        visiting, visited = set(), set()
        def visit(cid):
            if cid in visiting:
                raise RegistryError(f"dependency cycle at {cid}")
            if cid in visited:
                return
            visiting.add(cid)
            for dep in components[cid]["depends_on"]:
                visit(dep)
            visiting.remove(cid)
            visited.add(cid)
        for cid in components:
            visit(cid)
        for rid, req in requirements.items():
            _nonempty(req.get("statement"), f"{rid}.statement")
            _nonempty(req.get("verification_method"), f"{rid}.verification_method")
            _nonempty(req.get("acceptance_criteria"), f"{rid}.acceptance_criteria")
            if req.get("status") not in STATUSES:
                raise RegistryError(f"{rid}: invalid status")
            targets = req.get("component_ids")
            if not isinstance(targets, list) or not targets or len(targets)!=len(set(targets)):
                raise RegistryError(f"{rid}: invalid component_ids")
            for target in targets:
                if target not in components:
                    raise RegistryError(f"{rid}: missing component {target}")
        return cls(components, requirements, data["schema_version"])

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def dependencies_first(self) -> list[str]:
        order, seen = [], set()
        def visit(cid):
            if cid in seen: return
            for dep in self.components[cid]["depends_on"]: visit(dep)
            seen.add(cid); order.append(cid)
        for cid in sorted(self.components): visit(cid)
        return order

    def trace(self, component_id: str) -> list[str]:
        if component_id not in self.components:
            raise RegistryError(f"unknown component {component_id}")
        return sorted(rid for rid, req in self.requirements.items() if component_id in req["component_ids"])
