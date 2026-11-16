import unittest,random
from island.consistency import Scenario,assess_scenarios,escalate_asset_risks
from island.transient import HeadSample,HeadSeries,TransientPath
from island.groundwater import Interval
from island.geotechnics import GeotechnicalInputError

class ConsistencyTests(unittest.TestCase):
    def path(self,up=((0,4,5),(10,6,7)),down=((0,1,2),(10,1,2)),k=Interval(1e-5,2e-5)):
        def series(name,pts):
            return HeadSeries(name,tuple(HeadSample(t,None if lo is None else Interval(lo,hi)) for t,lo,hi in pts))
        return TransientPath('P',series('UP',up),series('DOWN',down),10,k,2)
    def scenario(self,name='A',path=None,a=0,b=10):return Scenario(name,path or self.path(),a,b)
    def test_union(self):
        a=self.scenario();b=self.scenario('B',self.path(up=((0,8,9),(10,9,10))))
        result=assess_scenarios((a,b))
        self.assertTrue(result['complete']);self.assertEqual(result['gradient'],{'low':.2,'high':.9})
        self.assertIn('MULTI_SCENARIO_UNCERTAINTY',result['risk_flags'])
    def test_unknown_interior_fails_closed(self):
        s=self.scenario(path=self.path(up=((0,4,5),(5,None,None),(10,6,7))))
        r=assess_scenarios((s,));self.assertFalse(r['complete']);self.assertIsNone(r['gradient'])
        self.assertIn('CONSERVATIVE_ESCALATION_REQUIRED',r['risk_flags'])
    def test_unknown_conductivity_fails_closed(self):
        r=assess_scenarios((self.scenario(path=self.path(k=None)),))
        self.assertFalse(r['complete']);self.assertIsNone(r['discharge_m3_s'])
    def test_incompatible_windows_paths_and_ids(self):
        for scenarios in ((self.scenario(),self.scenario()),(self.scenario(),self.scenario('B',a=1)),()):
            with self.assertRaises(GeotechnicalInputError):assess_scenarios(scenarios)
        p=self.path();q=TransientPath('Q',p.upstream,p.downstream,10,p.conductivity_m_s,2)
        with self.assertRaises(GeotechnicalInputError):assess_scenarios((self.scenario(),self.scenario('B',q)))
    def test_boundary_rejection(self):
        for a,b in [(-1,5),(0,11),(9,8)]:
            with self.assertRaises(GeotechnicalInputError):assess_scenarios((self.scenario(a=a,b=b),))
    def test_edge_isolation_and_escalation(self):
        a=assess_scenarios((self.scenario(path=self.path(k=None)),))
        b=assess_scenarios((self.scenario(),))
        inputs={'A':a,'B':b}
        self.assertNotIn('CONSERVATIVE_ESCALATION_REQUIRED',escalate_asset_risks(inputs,{'B':('A',)},set())['B'])
        self.assertIn('CONSERVATIVE_ESCALATION_REQUIRED',escalate_asset_risks(inputs,{'B':('A',)},{('A','B')})['B'])
        with self.assertRaises(GeotechnicalInputError):escalate_asset_risks(inputs,{'B':('A',)},{('B','A')})
    def test_invalid_assessments(self):
        with self.assertRaises(GeotechnicalInputError):escalate_asset_risks({'A':{'complete':True,'risk_flags':[],'engineering_approval':'GO'}},{},set())
        with self.assertRaises(GeotechnicalInputError):assess_scenarios([self.scenario()])
    def test_single_instant(self):
        self.assertTrue(assess_scenarios((self.scenario(a=5,b=5),))['complete'])
    def test_property_union_encloses_each_scenario(self):
        rng=random.Random(605)
        for _ in range(1200):
            a=rng.uniform(2,4);b=rng.uniform(5,9)
            p=self.path(up=((0,a,a+1),(10,b,b+1)))
            q=self.path(up=((0,b,b+1),(10,a,a+1)))
            combined=assess_scenarios((self.scenario('A',p),self.scenario('B',q)))
            for scenario in (self.scenario('A',p),self.scenario('B',q)):
                single=assess_scenarios((scenario,))
                for key in ('gradient','specific_discharge_m_s','discharge_m3_s'):
                    self.assertLessEqual(combined[key]['low'],single[key]['low'])
                    self.assertGreaterEqual(combined[key]['high'],single[key]['high'])
    def test_no_approval(self):
        self.assertEqual(assess_scenarios((self.scenario(),))['engineering_approval'],'BLOCKED/NO-GO')
