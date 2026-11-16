import unittest, random, math
from island.transient import HeadSample,HeadSeries,TransientPath,transient_envelope,transient_asset_risks
from island.groundwater import Interval
from island.geotechnics import GeotechnicalInputError
from island.seepage import HydraulicBoundary,SeepagePath,seepage_screen

class TransientTests(unittest.TestCase):
    def series(self,name,points):
        return HeadSeries(name,tuple(HeadSample(t,v) for t,v in points))
    def path(self,up=None,down=None,k=Interval(1e-5,2e-5)):
        return TransientPath('P',up or self.series('UP',[(0,Interval(4,5)),(10,Interval(6,7))]),
                             down or self.series('DOWN',[(0,Interval(1,2)),(10,Interval(1,2))]),10,k,2)
    def test_basic_envelope(self):
        r=transient_envelope(self.path(),0,10,Interval(.2,.4))
        self.assertEqual(r['gradient'],{'low':.2,'high':.6})
        self.assertIn('POTENTIAL_CRITICAL_GRADIENT',r['risk_flags'])
        self.assertEqual(r['engineering_approval'],'BLOCKED/NO-GO')
    def test_asynchronous_knots(self):
        p=self.path(up=self.series('UP',[(0,Interval(4,4)),(5,Interval(9,9)),(10,Interval(4,4))]))
        r=transient_envelope(p,0,10)
        self.assertEqual(r['evaluated_times_days'],[0,5,10]);self.assertEqual(r['gradient']['high'],.8)
    def test_no_extrapolation(self):
        for a,b in [(-1,5),(0,11),(8,7)]:
            with self.assertRaises(GeotechnicalInputError): transient_envelope(self.path(),a,b)
    def test_invalid_series(self):
        for pts in [[],[(1,Interval(0,1)),(1,Interval(1,2))],[(2,Interval(0,1)),(1,Interval(0,1))]]:
            with self.assertRaises(GeotechnicalInputError): self.series('A',pts)
        for t in [float('nan'),float('inf'),-1]:
            with self.assertRaises(GeotechnicalInputError): HeadSample(t,Interval(0,1))
        with self.assertRaises(GeotechnicalInputError): self.series('A',[(0,Interval(0,1))]).at(1)
    def test_unknown_at_knot_blocks_envelope(self):
        p=self.path(up=self.series('UP',[(0,Interval(4,5)),(5,None),(10,Interval(4,5))]))
        r=transient_envelope(p,0,10)
        self.assertIsNone(r['gradient']);self.assertIsNone(r['discharge_m3_s'])
        self.assertIn('TEMPORAL_ENVELOPE_UNKNOWN',r['risk_flags'])
    def test_unknown_conductivity(self):
        r=transient_envelope(self.path(k=None),0,10)
        self.assertIsNone(r['gradient']);self.assertIn('TEMPORAL_ENVELOPE_UNKNOWN',r['risk_flags'])
    def test_reject_geometry_and_types(self):
        with self.assertRaises(GeotechnicalInputError): self.path(k=Interval(-1,1))
        with self.assertRaises(GeotechnicalInputError): transient_envelope('bad',0,1)
        with self.assertRaises(GeotechnicalInputError): transient_envelope(self.path(),0,10,Interval(0,1))
        with self.assertRaises(GeotechnicalInputError): TransientPath('P',self.series('X',[(0,Interval(1,2))]),self.series('X',[(0,Interval(2,3))]),1,Interval(1,2),1)
    def test_single_instant(self):
        r=transient_envelope(self.path(),5,5)
        self.assertEqual(r['evaluated_times_days'],[5])
    def test_isolation(self):
        e={'A':{'risk_flags':['FLOOD'],'engineering_approval':'BLOCKED/NO-GO'},'B':{'risk_flags':[],'engineering_approval':'BLOCKED/NO-GO'}}
        self.assertEqual(transient_asset_risks(e,{'B':('A',)},set())['B'],[])
        self.assertEqual(transient_asset_risks(e,{'B':('A',)},{('A','B')})['B'],['FLOOD'])
        with self.assertRaises(GeotechnicalInputError): transient_asset_risks({'A':{'risk_flags':[],'engineering_approval':'GO'}},{},set())
    def test_property_enclosure(self):
        rng=random.Random(504)
        for _ in range(2000):
            ts=sorted(rng.sample(range(1,99),3)); ts=[0]+ts+[100]
            up=[(t,Interval(rng.uniform(2,5),rng.uniform(6,10))) for t in ts]
            down=[(t,Interval(rng.uniform(-2,0),rng.uniform(0,2))) for t in [0,25,50,75,100]]
            p=self.path(self.series('UP',up),self.series('DOWN',down))
            env=transient_envelope(p,0,100)
            for _ in range(4):
                t=rng.uniform(0,100)
                a=p.upstream.at(t);b=p.downstream.at(t)
                g=(rng.uniform(a.low,a.high)-rng.uniform(b.low,b.high))/10
                k=rng.uniform(1e-5,2e-5)
                q=g*k*2
                self.assertLessEqual(env['gradient']['low']-1e-8,g)
                self.assertGreaterEqual(env['gradient']['high']+1e-8,g)
                self.assertLessEqual(env['discharge_m3_s']['low']-1e-8,q)
                self.assertGreaterEqual(env['discharge_m3_s']['high']+1e-8,q)
