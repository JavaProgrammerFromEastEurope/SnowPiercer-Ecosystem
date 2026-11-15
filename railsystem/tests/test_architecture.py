import copy
import unittest
from pathlib import Path
from railsystem.architecture import ArchitectureError, load_registry, validate_registry

REGISTRY = Path(__file__).resolve().parents[1] / "architecture" / "registry.json"

class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.data = load_registry(REGISTRY)

    def test_registry_valid(self):
        self.assertTrue(validate_registry(self.data))

    def test_eight_components_and_interfaces(self):
        self.assertEqual(len(self.data["components"]), 8)
        self.assertEqual(len(self.data["external_interfaces"]), 8)

    def test_unknown_dependency_rejected(self):
        self.data["components"][0]["depends_on"] = ["missing"]
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_cycle_rejected(self):
        self.data["components"][4]["depends_on"] = ["rolling_stock"]
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_duplicate_component_rejected(self):
        self.data["components"].append(copy.deepcopy(self.data["components"][0]))
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_self_dependency_rejected(self):
        self.data["components"][0]["depends_on"] = ["rolling_stock"]
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_actuation_rejected(self):
        self.data["external_interfaces"][0]["actuation_allowed"] = True
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_missing_criticality_rejected(self):
        del self.data["components"][0]["criticality"]
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_duplicate_interface_rejected(self):
        self.data["external_interfaces"].append(copy.deepcopy(self.data["external_interfaces"][0]))
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

    def test_empty_registry_rejected(self):
        self.data["components"] = []
        with self.assertRaises(ArchitectureError): validate_registry(self.data)

if __name__ == "__main__": unittest.main()
