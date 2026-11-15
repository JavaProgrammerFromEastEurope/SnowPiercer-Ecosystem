import copy
import json
import unittest
from pathlib import Path
from lifesupport.core.registry import Registry, RegistryError
from lifesupport.core.contracts import validate_envelope

DATA = json.loads((Path(__file__).resolve().parents[1] / "data" / "registry.json").read_text())

class RegistryTests(unittest.TestCase):
    def test_baseline(self):
        r = Registry.from_dict(DATA)
        self.assertEqual(len(r.components), 20)
        self.assertEqual(len(r.requirements), 24)
        self.assertEqual(r.dependencies_first()[0], "LIFE-CORE-001")
    def test_trace(self):
        r = Registry.from_dict(DATA)
        self.assertIn("LREQ-023", r.trace("LIFE-CONTROL-001"))
    def test_duplicate_component(self):
        d=copy.deepcopy(DATA);d["components"].append(copy.deepcopy(d["components"][0]))
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_missing_dependency(self):
        d=copy.deepcopy(DATA);d["components"][1]["depends_on"]=["LIFE-UNKNOWN-001"]
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_self_dependency(self):
        d=copy.deepcopy(DATA);d["components"][0]["depends_on"]=["LIFE-CORE-001"]
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_cycle(self):
        d=copy.deepcopy(DATA);d["components"][0]["depends_on"]=["LIFE-ATMOSPHERE-001"]
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_dangling_requirement(self):
        d=copy.deepcopy(DATA);d["requirements"][0]["component_ids"]=["LIFE-UNKNOWN-001"]
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_duplicate_requirement(self):
        d=copy.deepcopy(DATA);d["requirements"].append(copy.deepcopy(d["requirements"][0]))
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_unknown_area(self):
        d=copy.deepcopy(DATA);d["components"][0]["area"]="UNLISTED"
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_invalid_status(self):
        d=copy.deepcopy(DATA);d["requirements"][0]["status"]="ready"
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_empty_acceptance(self):
        d=copy.deepcopy(DATA);d["requirements"][0]["acceptance_criteria"]=""
        with self.assertRaises(RegistryError): Registry.from_dict(d)
    def test_unsupported_schema(self):
        d=copy.deepcopy(DATA);d["schema_version"]="2.0"
        with self.assertRaises(RegistryError): Registry.from_dict(d)

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.msg={"schema_version":"1.0","kind":"LifeTelemetry","source_component_id":"LIFE-SENSORS-001","message_id":"msg-001","timestamp_utc":"2026-11-14T00:00:00Z","payload":{"temperature_c":21.5}}
        self.ids=set(Registry.from_dict(DATA).components)
    def test_valid_telemetry(self): self.assertEqual(validate_envelope(self.msg,self.ids),self.msg)
    def test_command_disabled(self):
        m=dict(self.msg,kind="LifeCommand")
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)
    def test_unknown_source(self):
        m=dict(self.msg,source_component_id="OTHER")
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)
    def test_naive_timestamp(self):
        m=dict(self.msg,timestamp_utc="2026-11-14T00:00:00")
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)
    def test_bad_payload(self):
        m=dict(self.msg,payload=[])
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)
    def test_unknown_kind(self):
        m=dict(self.msg,kind="LifeExploit")
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)
    def test_unsupported_version(self):
        m=dict(self.msg,schema_version="9.0")
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)
    def test_bad_timestamp(self):
        m=dict(self.msg,timestamp_utc="invalid")
        with self.assertRaises(RegistryError): validate_envelope(m,self.ids)

if __name__ == "__main__": unittest.main()
