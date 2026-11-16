import json, random, unittest
from island.geotechnics import Layer,Site,GeotechnicalInputError
from island.groundwater import Interval,WaterObservation,GroundwaterSeries,Scenario,interval_screen,propagate_risks
from island.validation import ROOT

def fixture():
    site=Site((Layer('fill',0,2,18,'fill'),Layer('sand',2,10,20,'soil')),3,100,20)
    series=GroundwaterSeries((WaterObservation(0,Interval(2,4)),WaterObservation(10,Interval(4,6))))
    scenario=Scenario('SYN-GEO-002',5,series,(Interval(17,19),Interval(19,21)))
    return site,series,scenario

class Stage003Tests(unittest.TestCase):
    def test_reference(self):
        s,_,sc=fixture(); result=interval_screen(s,sc,5)
        self.assertEqual(result['total_vertical_stress_kpa'],{'low':91,'high':101})
        self.assertEqual(result['hydrostatic_pore_pressure_kpa'],{'low':0,'high':19.62})
        self.assertEqual(result['effective_vertical_stress_kpa'],{'low':71.38,'high':101})
        self.assertEqual(result['engineering_approval'],'BLOCKED/NO-GO')
    def test_water_interpolation(self):
        _,series,_=fixture()
        self.assertEqual(series.at(5),Interval(3,5))
        self.assertEqual(series.at(0),Interval(2,4))
        self.assertEqual(series.at(10),Interval(4,6))
    def test_unknown_never_dry(self):
        s,_,sc=fixture()
        unknown=Scenario('unknown',5,GroundwaterSeries((WaterObservation(0,None),WaterObservation(10,Interval(1,2)))),sc.unit_weights)
        out=interval_screen(s,unknown,5)
        self.assertIsNone(out['effective_vertical_stress_kpa'])
        self.assertIn('GROUNDWATER_UNKNOWN',out['risk_flags'])
    def test_extrapolation_and_time_validation(self):
        _,series,_=fixture()
        for time in [-1,11,float('nan'),float('inf')]:
            with self.subTest(time=time),self.assertRaises(GeotechnicalInputError): series.at(time)
        with self.assertRaises(GeotechnicalInputError): GroundwaterSeries((WaterObservation(1,Interval(1,2)),WaterObservation(1,Interval(1,2))))
        with self.assertRaises(GeotechnicalInputError): GroundwaterSeries((WaterObservation(2,Interval(1,2)),WaterObservation(1,Interval(1,2))))
    def test_interval_invalid(self):
        for a,b in [(2,1),(float('nan'),1),(0,float('inf'))]:
            with self.subTest(a=a,b=b),self.assertRaises(GeotechnicalInputError): Interval(a,b)
        with self.assertRaises(GeotechnicalInputError): WaterObservation(1,Interval(-1,1))
    def test_mismatch_and_depth(self):
        s,series,sc=fixture()
        with self.assertRaises(GeotechnicalInputError): interval_screen(s,Scenario('bad',5,series,(Interval(1,2),)),5)
        with self.assertRaises(GeotechnicalInputError): interval_screen(s,sc,11)
        with self.assertRaises(GeotechnicalInputError): Scenario('bad',5,series,(Interval(0,2),))
    def test_graph_cycles_and_isolation(self):
        graph={'A':('B',),'B':('A',),'C':('B',),'D':()}
        result=propagate_risks({'A':{'FLOOD'},'D':{'ISOLATED'}},graph)
        self.assertEqual(result['C'],['FLOOD'])
        self.assertEqual(result['D'],['ISOLATED'])
    def test_graph_invalid(self):
        with self.assertRaises(GeotechnicalInputError): propagate_risks({'A':{'F'}},{'A':('missing',)})
        with self.assertRaises(GeotechnicalInputError): propagate_risks({}, {})
    def test_property_random_intervals(self):
        rng=random.Random(20261114)
        for _ in range(1500):
            s,series,_=fixture()
            depth=rng.uniform(0,10)
            w1=rng.uniform(10,25);w2=rng.uniform(10,25)
            sc=Scenario('property',rng.uniform(0,10),series,(Interval(w1,w1+rng.uniform(0,5)),Interval(w2,w2+rng.uniform(0,5))))
            out=interval_screen(s,sc,depth)
            t=out['total_vertical_stress_kpa']; p=out['hydrostatic_pore_pressure_kpa']; e=out['effective_vertical_stress_kpa']
            self.assertLessEqual(t['low'],t['high']);self.assertLessEqual(p['low'],p['high'])
            self.assertLessEqual(e['low'],e['high'])
            self.assertAlmostEqual(e['low'],t['low']-p['high'],places=5)
            self.assertAlmostEqual(e['high'],t['high']-p['low'],places=5)
            self.assertEqual(out['engineering_approval'],'BLOCKED/NO-GO')
    def test_property_monotone_risk(self):
        rng=random.Random(123)
        for _ in range(300):
            graph={f'N{i}':tuple(f'N{j}' for j in range(5) if rng.random()<0.25) for i in range(5)}
            seeds={'N0':{'HAZARD'}}
            result=propagate_risks(seeds,graph)
            self.assertIn('HAZARD',result['N0'])
            for n,up in graph.items():
                for u in up: self.assertTrue(set(result[u]).issubset(set(result[n])))
    def test_artifact_traceability(self):
        req=json.loads((ROOT/'models/requirements.json').read_text())['requirements']
        new=[x for x in req if x['id'].startswith('ISLAND-GEO2-')]
        self.assertEqual(len(new),8)
        self.assertTrue(all(x['verification'] and x['evidence'] for x in new))
        self.assertEqual(json.loads((ROOT/'models/readiness.json').read_text())['physical_deployment'],'BLOCKED/NO-GO')
