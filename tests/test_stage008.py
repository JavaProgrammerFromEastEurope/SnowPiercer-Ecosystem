import json, tempfile, unittest, random
from pathlib import Path
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from island.trusted_measurements import *
from island.groundwater import Interval
from island.transient import HeadSample,HeadSeries,TransientPath
from island.consistency import Scenario
from island.provenance import EvidenceRecord,ScenarioEvidence
from island.geotechnics import GeotechnicalInputError

class TrustTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Ed25519PrivateKey.generate();self.source=Ed25519PrivateKey.generate()
        raw=lambda k:k.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        pol=canonical({'policy_version':2,'sources':{'probe-A':{'version':1,'public_key':raw(self.source).hex()}}})
        self.policy=TrustPolicy(raw(self.root),pol,self.root.sign(b'ISLAND-POLICY-V1\x00'+pol))
        self.ledger=ReplayLedger(Path(self.tmp.name)/'replay.sqlite')
        upstream=HeadSeries('up',(HeadSample(0,Interval(4,5)),HeadSample(1,Interval(4,5))))
        downstream=HeadSeries('down',(HeadSample(0,Interval(1,2)),HeadSample(1,Interval(1,2))))
        path=TransientPath('path',upstream,downstream,10,Interval(0.00001,0.00002),2)
        self.scenario=Scenario('s',path,0,1)
        self.epoch='2026-01-01T00:00:00Z'
    def make(self,modify=None):
        ids=['up@0','up@1','down@0','down@1','path@conductivity']
        records=[]; signed={}
        for n,oid in enumerate(ids,1):
            kind='conductivity' if n==5 else 'head'
            lo,hi=('0.00001','0.00002') if n==5 else (('4','5') if n<=2 else ('1','2'))
            m={'source_id':'probe-A','source_version':1,'observation_id':oid,'kind':kind,'unit':('m/s' if n==5 else 'm'),
               'time_utc':('2026-01-02T00:00:00Z' if n in (2,4) else self.epoch),'low':lo,'high':hi,'sequence':n}
            if modify: modify(m,n)
            payload=canonical(m);eid='e'+str(n)
            records.append(EvidenceRecord(eid,'probe-A',1,sha256(payload).hexdigest(),oid))
            signed[eid]=SignedMeasurement(payload,self.source.sign(b'ISLAND-MEASUREMENT-V1\x00'+payload))
        return (ScenarioEvidence(self.scenario,tuple(records)),),signed
    def assess(self,modify=None,policy=None,ledger=None):
        items,signed=self.make(modify)
        return admit_signed_measurements(items,signed,policy or self.policy,ledger or self.ledger,self.epoch)
    def test_valid(self): self.assertTrue(self.assess()['admitted'])
    def test_replay(self):
        self.assertTrue(self.assess()['admitted']); r=self.assess();self.assertFalse(r['admitted']);self.assertIn('CONSERVATIVE_ESCALATION_REQUIRED',r['risk_flags'])
    def test_numeric_tamper(self): self.assertFalse(self.assess(lambda m,n:m.update(low='8') if n==1 else None)['admitted'])
    def test_time_tamper(self): self.assertFalse(self.assess(lambda m,n:m.update(time_utc='2026-01-03T00:00:00Z') if n==1 else None)['admitted'])
    def test_unit_tamper(self): self.assertFalse(self.assess(lambda m,n:m.update(unit='ft') if n==1 else None)['admitted'])
    def test_source_tamper(self): self.assertFalse(self.assess(lambda m,n:m.update(source_id='evil') if n==1 else None)['admitted'])
    def test_policy_signature_tamper(self):
        bad=TrustPolicy(self.policy.root_public_key,self.policy.policy_payload,b'0'*64)
        self.assertFalse(self.assess(policy=bad)['admitted'])
    def test_signature_tamper(self):
        items,signed=self.make();signed['e1']=SignedMeasurement(signed['e1'].payload,b'0'*64)
        self.assertFalse(admit_signed_measurements(items,signed,self.policy,self.ledger,self.epoch)['admitted'])
    def test_missing(self):
        items,signed=self.make();del signed['e1']
        self.assertFalse(admit_signed_measurements(items,signed,self.policy,self.ledger,self.epoch)['admitted'])
    def test_duplicate_json(self):
        with self.assertRaises(GeotechnicalInputError):parse_canonical(b'{"a":1,"a":2}')
    def test_noncanonical(self):
        with self.assertRaises(GeotechnicalInputError):parse_canonical(b'{"b":2, "a":1}')
    def test_nan(self):
        with self.assertRaises(GeotechnicalInputError):validate_measurement({'source_id':'x','source_version':1,'observation_id':'o','kind':'head','unit':'m','time_utc':self.epoch,'low':'NaN','high':'1','sequence':1})
    def test_policy_rollback(self):
        self.assertTrue(self.assess()['admitted'])
        pol=canonical({'policy_version':1,'sources':json.loads(self.policy.policy_payload)['sources']})
        old=TrustPolicy(self.policy.root_public_key,pol,self.root.sign(b'ISLAND-POLICY-V1\x00'+pol))
        self.assertFalse(self.assess(policy=old)['admitted'])
    def test_property_roundtrip(self):
        rng=random.Random(71)
        for _ in range(1200):
            v=rng.randint(-10**9,10**9)
            obj={'a':str(v),'z':[v,True,None]}
            self.assertEqual(parse_canonical(canonical(obj)),obj)
    def test_property_tamper(self):
        rng=random.Random(9)
        for _ in range(300):
            payload=canonical({'x':rng.randint(0,10**10)})
            signature=self.source.sign(b'ISLAND-MEASUREMENT-V1\x00'+payload)
            tampered=payload+b' '
            with self.assertRaises(Exception):self.source.public_key().verify(signature,b'ISLAND-MEASUREMENT-V1\x00'+tampered)
    def test_concurrent_ledger(self):
        import concurrent.futures
        items,signed=self.make()
        def run(_):return admit_signed_measurements(items,signed,self.policy,self.ledger,self.epoch)['admitted']
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: outcomes=list(pool.map(run,range(8)))
        self.assertEqual(outcomes.count(True),1)
