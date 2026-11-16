import unittest,random,math
from island.seepage import HydraulicBoundary,SeepagePath,seepage_screen,isolated_risk_propagation
from island.groundwater import Interval
from island.geotechnics import GeotechnicalInputError

class TestSeepage(unittest.TestCase):
    def path(self,a=Interval(4,5),b=Interval(1,2),k=Interval(.00001,.00002),length=10,area=2):
        return SeepagePath('SYN',HydraulicBoundary('UP',a),HydraulicBoundary('DOWN',b),length,k,area)
    def test_nominal(self):
        r=seepage_screen(self.path(),Interval(.2,.4))
        self.assertEqual(r['gradient'],{'low':.2,'high':.4})
        self.assertIn('POTENTIAL_CRITICAL_GRADIENT',r['risk_flags'])
        self.assertEqual(r['engineering_approval'],'BLOCKED/NO-GO')
    def test_unknown_is_fail_closed(self):
        for p in [self.path(a=None),self.path(b=None),self.path(k=None)]:
            r=seepage_screen(p)
            self.assertIsNone(r['gradient']);self.assertIsNone(r['discharge_m3_s'])
            self.assertIn('HYDRAULIC_INPUT_UNKNOWN',r['risk_flags'])
    def test_invalid(self):
        for length,area in [(0,2),(-1,2),(10,0),(10,-1),(float('nan'),2),(float('inf'),2)]:
            with self.assertRaises(GeotechnicalInputError): self.path(length=length,area=area)
        with self.assertRaises(GeotechnicalInputError): self.path(k=Interval(-1,1))
        with self.assertRaises(GeotechnicalInputError): seepage_screen(self.path(),Interval(0,1))
        with self.assertRaises(GeotechnicalInputError): seepage_screen('bad')
    def test_reverse_flow(self):
        r=seepage_screen(self.path(a=Interval(0,1),b=Interval(4,5)))
        self.assertLess(r['discharge_m3_s']['high'],0)
    def test_direction_ambiguity(self):
        r=seepage_screen(self.path(a=Interval(1,5),b=Interval(2,4)))
        self.assertIn('FLOW_DIRECTION_UNCERTAIN',r['risk_flags'])
    def test_property_interval_enclosure(self):
        rng=random.Random(20261114)
        for _ in range(2000):
            al=rng.uniform(-10,10); ah=al+rng.uniform(0,10)
            bl=rng.uniform(-10,10); bh=bl+rng.uniform(0,10)
            kl=rng.uniform(0,0.001);kh=kl+rng.uniform(0,0.001)
            length=rng.uniform(.1,100);area=rng.uniform(.1,50)
            r=seepage_screen(self.path(Interval(al,ah),Interval(bl,bh),Interval(kl,kh),length,area))
            for _ in range(3):
                a=rng.uniform(al,ah);b=rng.uniform(bl,bh);k=rng.uniform(kl,kh)
                g=(a-b)/length; q=k*g*area
                self.assertLessEqual(r['gradient']['low']-1e-8,g)
                self.assertGreaterEqual(r['gradient']['high']+1e-8,g)
                self.assertLessEqual(r['discharge_m3_s']['low']-1e-8,q)
                self.assertGreaterEqual(r['discharge_m3_s']['high']+1e-8,q)
    def test_isolation_and_cycles(self):
        seeds={'A':{'FLOOD'},'B':set(),'C':set()}
        deps={'B':('A','C'),'C':('B',)}
        r=isolated_risk_propagation(seeds,deps,{('B','C')})
        self.assertEqual(r['B'],[]);self.assertEqual(r['C'],[])
        r=isolated_risk_propagation(seeds,deps,{('A','B'),('B','C'),('C','B')})
        self.assertEqual(r['C'],['FLOOD'])
    def test_reject_undeclared_edges(self):
        with self.assertRaises(GeotechnicalInputError):
            isolated_risk_propagation({'A':set(),'B':set()},{'B':('A',)},{('B','A')})
    def test_property_isolation(self):
        rng=random.Random(22)
        for _ in range(500):
            n=7; nodes=[str(i) for i in range(n)]
            deps={v:tuple(u for u in nodes if u!=v and rng.random()<.2) for v in nodes}
            edges={(u,v) for v,ss in deps.items() for u in ss if rng.random()<.5}
            r=isolated_risk_propagation({'0':{'HAZARD'}},deps,edges)
            reachable={'0'}
            while True:
                more=reachable|{v for u,v in edges if u in reachable}
                if more==reachable:break
                reachable=more
            self.assertEqual({v for v in nodes if 'HAZARD' in r[v]},reachable)
