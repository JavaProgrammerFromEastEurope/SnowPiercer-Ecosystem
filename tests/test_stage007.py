import unittest,random
from dataclasses import replace
from island.provenance import EvidenceRecord,SourcePolicy,ScenarioEvidence,evidence_digest,admit_scenarios,propagate_admission_risks
from island.consistency import Scenario
from island.transient import HeadSample,HeadSeries,TransientPath
from island.groundwater import Interval
from island.geotechnics import GeotechnicalInputError

def fixture():
    u=HeadSeries('u',(HeadSample(0,Interval(4,5)),HeadSample(10,Interval(5,6))))
    d=HeadSeries('d',(HeadSample(0,Interval(1,2)),HeadSample(10,Interval(2,3))))
    s=Scenario('scenario',TransientPath('path',u,d,10,Interval(1e-5,2e-5),2),0,10)
    obs=['u@0','u@10','d@0','d@10','path@conductivity']
    records=tuple(EvidenceRecord('e'+str(j),'source',1,evidence_digest(x.encode()),x) for j,x in enumerate(obs))
    payloads={r.evidence_id:r.observation_id.encode() for r in records}
    policy=(SourcePolicy('source',1,frozenset(r.payload_sha256 for r in records)),)
    return (ScenarioEvidence(s,records),),policy,payloads

class Stage007(unittest.TestCase):
    def test_admitted(self):
        i,p,b=fixture();a=admit_scenarios(i,p,b)
        self.assertTrue(a['admitted']);self.assertIsNotNone(a['gradient']);self.assertEqual(len(a['trace']),5)
        self.assertEqual(a['engineering_approval'],'BLOCKED/NO-GO')
    def test_unknown_source(self):
        i,p,b=fixture();a=admit_scenarios(i,(),b)
        self.assertFalse(a['admitted']);self.assertIsNone(a['gradient']);self.assertIn('SOURCE_NOT_ADMITTED',a['reasons'])
    def test_missing_payload(self):
        i,p,b=fixture();b.pop('e0');self.assertIn('EVIDENCE_MISSING',admit_scenarios(i,p,b)['reasons'])
    def test_tamper(self):
        i,p,b=fixture();b['e0']=b'tampered';self.assertIn('EVIDENCE_DIGEST_MISMATCH',admit_scenarios(i,p,b)['reasons'])
    def test_version(self):
        i,p,b=fixture();p=(replace(p[0],admitted_version=2),)
        self.assertIn('SOURCE_VERSION_MISMATCH',admit_scenarios(i,p,b)['reasons'])
    def test_missing_observation(self):
        i,p,b=fixture();i=(replace(i[0],records=i[0].records[:-1]),)
        self.assertIn('OBSERVATION_COVERAGE_MISMATCH',admit_scenarios(i,p,b)['reasons'])
    def test_duplicate(self):
        i,p,b=fixture();i=(replace(i[0],records=i[0].records+(i[0].records[0],)),)
        self.assertIn('DUPLICATE_EVIDENCE_ID',admit_scenarios(i,p,b)['reasons'])
    def test_invalid_digest(self):
        with self.assertRaises(GeotechnicalInputError): EvidenceRecord('x','s',1,'0'*63,'o')
    def test_invalid_version_bool(self):
        with self.assertRaises(GeotechnicalInputError): SourcePolicy('s',True,frozenset({'a'*64}))
    def test_unknown_head(self):
        i,p,b=fixture();path=i[0].scenario.path
        u=HeadSeries('u',(HeadSample(0,None),path.upstream.samples[1]))
        i=(ScenarioEvidence(replace(i[0].scenario,path=replace(path,upstream=u)),i[0].records),)
        a=admit_scenarios(i,p,b);self.assertFalse(a['admitted']);self.assertIsNone(a['gradient'])
    def test_risk_isolation(self):
        i,p,b=fixture();a=admit_scenarios(i,(),b)
        result=propagate_admission_risks({'a':a,'b':a,'c':a},{'b':('a',),'c':('b',)}, {('a','b')})
        self.assertIn('PROVENANCE_ADMISSION_DENIED',result['b'])
        self.assertIn('PROVENANCE_ADMISSION_DENIED',result['c']) # seeded in c too
        result=propagate_admission_risks({'a':a,'b':{'admitted':True,'risk_flags':[],'engineering_approval':'BLOCKED/NO-GO'},'c':{'admitted':True,'risk_flags':[],'engineering_approval':'BLOCKED/NO-GO'}},{'b':('a',),'c':('b',)},{('a','b')})
        self.assertIn('PROVENANCE_ADMISSION_DENIED',result['b']);self.assertNotIn('PROVENANCE_ADMISSION_DENIED',result['c'])
    def test_property_mutations(self):
        rng=random.Random(706)
        for _ in range(1000):
            i,p,b=fixture();idx=rng.randrange(5)
            b['e'+str(idx)]=rng.randbytes(rng.randrange(1,64))
            a=admit_scenarios(i,p,b)
            self.assertFalse(a['admitted']);self.assertIsNone(a['gradient']);self.assertEqual(a['engineering_approval'],'BLOCKED/NO-GO')
    def test_property_permutations(self):
        rng=random.Random(707)
        for _ in range(500):
            i,p,b=fixture();rs=list(i[0].records);rng.shuffle(rs)
            a=admit_scenarios((replace(i[0],records=tuple(rs)),),p,b)
            self.assertTrue(a['admitted']);self.assertIsNotNone(a['gradient'])
if __name__=='__main__':unittest.main()
