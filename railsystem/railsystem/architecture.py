"""Architecture inventory validation; no runtime control capabilities."""
import json
from pathlib import Path

CRITICALITIES = frozenset({"operational", "simulation", "safety_related", "safety_critical"})

class ArchitectureError(ValueError):
    pass

def load_registry(path):
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    validate_registry(data)
    return data

def validate_registry(data):
    if not isinstance(data, dict) or data.get("schema_version") != "1.0" or data.get("stage") != "RAIL-ARCH-001":
        raise ArchitectureError("Unsupported architecture schema or stage")
    components = data.get("components")
    interfaces = data.get("external_interfaces")
    if not isinstance(components, list) or not components or not isinstance(interfaces, list) or not interfaces:
        raise ArchitectureError("Nonempty components and external interfaces required")
    for group in (components, interfaces):
        ids = [item.get("id") for item in group if isinstance(item, dict)]
        if len(ids) != len(group) or any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
            raise ArchitectureError("Missing or duplicate identifiers")
    component_ids = {item["id"] for item in components}
    for item in components:
        if not isinstance(item.get("responsibility"), str) or not item["responsibility"].strip():
            raise ArchitectureError("Component responsibility required")
        if item.get("criticality") not in CRITICALITIES or item.get("implementation_status") != "planned":
            raise ArchitectureError("Invalid component classification or status")
        dependencies = item.get("depends_on")
        if not isinstance(dependencies, list) or len(dependencies) != len(set(dependencies)) or any(d not in component_ids or d == item["id"] for d in dependencies):
            raise ArchitectureError("Invalid component dependency")
    for item in interfaces:
        if not isinstance(item.get("purpose"), str) or not item["purpose"].strip() or item.get("contract_status") != "proposed" or item.get("actuation_allowed") is not False:
            raise ArchitectureError("Unsafe or incomplete external interface")
    visiting, visited = set(), set()
    graph = {item["id"]: item["depends_on"] for item in components}
    def visit(node):
        if node in visiting:
            raise ArchitectureError("Cyclic component dependency")
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)
    return True
