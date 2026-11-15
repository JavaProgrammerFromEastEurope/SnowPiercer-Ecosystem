import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from railsystem.integration import TrainOSBoundary, ContractError, load_interface_spec

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)

def message(kind='telemetry.report', **changes):
    data = dict(schema_version='1.0', message_id='m-1', kind=kind, source='sensor-1', timestamp=NOW.isoformat().replace('+00:00','Z'), payload={'asset_id':'train-1','metric':'speed','value':0.0,'unit':'km/h'})
    if kind == 'health.report': data['payload'] = {'asset_id':'train-1','state':'ok'}
    if kind == 'audit.event': data['payload'] = {'event_id':'evt-1','description':'test event'}
    data.update(changes)
    return json.dumps(data, allow_nan=False).encode()

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.boundary = TrainOSBoundary({'sensor-1': {'telemetry_publisher', 'health_publisher', 'audit_publisher'}}, now=lambda: NOW)
    def reject(self, raw, source='sensor-1'):
        with self.assertRaises(ContractError): self.boundary.receive(raw, source)
        self.assertEqual(self.boundary.audit[-1]['outcome'], 'rejected')
    def test_spec(self):
        p = Path(__file__).resolve().parents[1] / 'interfaces/trainos_v1.json'
        self.assertFalse(load_interface_spec(p)['actuation_allowed'])
    def test_telemetry(self): self.assertEqual(self.boundary.receive(message(), 'sensor-1').kind, 'telemetry.report')
    def test_health(self): self.assertEqual(self.boundary.receive(message('health.report'), 'sensor-1').kind, 'health.report')
    def test_audit(self): self.assertEqual(self.boundary.receive(message('audit.event'), 'sensor-1').kind, 'audit.event')
    def test_replay(self):
        self.boundary.receive(message(), 'sensor-1'); self.reject(message())
    def test_identity_spoof(self): self.reject(message(), 'other')
    def test_unknown_identity(self): self.reject(message(source='unknown'), 'unknown')
    def test_wrong_role(self):
        b = TrainOSBoundary({'sensor-1': {'health_publisher'}}, now=lambda: NOW)
        with self.assertRaises(ContractError): b.receive(message(), 'sensor-1')
    def test_command_rejected(self): self.reject(message(kind='traction.command'))
    def test_unknown_field(self):
        d = json.loads(message()); d['execute'] = True; self.reject(json.dumps(d).encode())
    def test_unknown_payload_field(self): self.reject(message(payload={'asset_id':'train-1','metric':'speed','value':1,'unit':'km/h','brake':True}))
    def test_invalid_version(self): self.reject(message(schema_version='2.0'))
    def test_old_timestamp(self): self.reject(message(timestamp=(NOW-timedelta(seconds=61)).isoformat().replace('+00:00','Z')))
    def test_future_timestamp(self): self.reject(message(timestamp=(NOW+timedelta(seconds=6)).isoformat().replace('+00:00','Z')))
    def test_bad_timestamp(self): self.reject(message(timestamp='bad'))
    def test_malformed_json(self): self.reject(b'{')
    def test_bad_utf8(self): self.reject(b'\xff')
    def test_size_limit(self): self.reject(b'x'*16385)
    def test_non_bytes(self): self.reject('not bytes')
    def test_boolean_value(self): self.reject(message(payload={'asset_id':'train-1','metric':'speed','value':True,'unit':'km/h'}))
    def test_missing_payload(self): self.reject(message(payload={}))
    def test_unauthorized_role_does_not_consume_id(self):
        b = TrainOSBoundary({'sensor-1': {'health_publisher'}}, now=lambda: NOW)
        with self.assertRaises(ContractError): b.receive(message(), 'sensor-1')
        self.assertEqual(len(b._seen), 0)
    def test_same_id_different_source(self):
        b = TrainOSBoundary({'sensor-1': {'telemetry_publisher'}, 'sensor-2': {'telemetry_publisher'}}, now=lambda: NOW)
        b.receive(message(), 'sensor-1')
        self.assertEqual(b.receive(message(source='sensor-2'), 'sensor-2').source, 'sensor-2')

if __name__ == '__main__': unittest.main()
