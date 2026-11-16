import json,math,random,unittest
from island.geotechnics import Layer,Site,screen,total_vertical_stress_kpa,hydrostatic_pore_pressure_kpa,GeotechnicalInputError
from island.validation import ROOT,validate

def layer(top=0,bottom=10,weight=20,material='soil'):
    return Layer('sample',top,bottom,weight,material)
def site(layers=None,groundwater=3,pressure=120,area=50,provenance='synthetic'):
    return Site(tuple(layers or [layer()]),groundwater,pressure,area,provenance)

class Stage002Tests(unittest.TestCase):
    def test_synthetic_case(self):
        case=json.loads((ROOT/'models/geotechnical_synthetic_case.json').read_text())
        layers=tuple(Layer(**x) for x in case['layers'])
        s=Site(layers,case['groundwater_depth_m'],case['surface_pressure_kpa'],case['footprint_m2'],case['provenance'])
        out=screen(s,case['evaluation_depth_m'])
        for k,v in case['expected'].items(): self.assertAlmostEqual(out[k],v)
    def test_layer_validation(self):
        for top,bottom,weight in [(0,0,20),(1,0,20),(-1,2,20),(0,2,0),(0,2,float('nan')),(0,2,float('inf'))]:
            with self.subTest(top=top,bottom=bottom,weight=weight),self.assertRaises(GeotechnicalInputError): layer(top,bottom,weight)
        for layers in [[],[layer(1,2)],[layer(0,2),layer(3,5)],[layer(0,3),layer(2,5)]]:
            with self.subTest(layers=layers),self.assertRaises(GeotechnicalInputError): Site(tuple(layers),3,10,10)
    def test_unknown_groundwater(self):
        result=screen(site(groundwater=None),5)
        self.assertIsNone(result['hydrostatic_pore_pressure_kpa'])
        self.assertIsNone(result['effective_vertical_stress_kpa'])
        self.assertIn('GROUNDWATER_UNKNOWN',result['risk_flags'])
    def test_depth_bounds(self):
        for d in [-1,10.00001,float('nan'),float('inf')]:
            with self.subTest(depth=d),self.assertRaises(GeotechnicalInputError): screen(site(),d)
        self.assertEqual(screen(site(),0)['total_vertical_stress_kpa'],0)
        self.assertEqual(screen(site(),10)['total_vertical_stress_kpa'],200)
    def test_risk_flags(self):
        self.assertIn('GROUNDWATER_INTERSECTION',screen(site(),5)['risk_flags'])
        self.assertIn('UNCERTAIN_STRATA',screen(site([layer(material='fill')]),5)['risk_flags'])
        self.assertNotIn('GROUNDWATER_INTERSECTION',screen(site(groundwater=8),5)['risk_flags'])
    def test_no_go(self):
        for provenance in ['synthetic','unverified-field','verified-field']:
            self.assertEqual(screen(site(provenance=provenance),5)['engineering_approval'],'BLOCKED/NO-GO')
        self.assertEqual(validate()['physical_deployment'],'BLOCKED/NO-GO')
    def test_invalid_loads_and_types(self):
        for pressure,area in [(-1,1),(0,0),(float('nan'),1),(True,1),(0,float('inf'))]:
            with self.subTest(pressure=pressure,area=area),self.assertRaises(GeotechnicalInputError): site(pressure=pressure,area=area)
        with self.assertRaises(GeotechnicalInputError): site(provenance='approved')
    def test_property_invariants(self):
        rng=random.Random(20261114)
        for _ in range(1000):
            split=rng.uniform(.01,9.99); w1=rng.uniform(10,30); w2=rng.uniform(10,30)
            s=site([layer(0,split,w1),layer(split,10,w2)],groundwater=rng.uniform(0,10),pressure=rng.uniform(0,500),area=rng.uniform(.1,1000))
            depth=rng.uniform(0,10)
            expected=min(depth,split)*w1+max(0,depth-split)*w2
            self.assertAlmostEqual(total_vertical_stress_kpa(s,depth),expected,places=8)
            self.assertGreaterEqual(hydrostatic_pore_pressure_kpa(s,depth),0)
            self.assertGreaterEqual(total_vertical_stress_kpa(s,10),total_vertical_stress_kpa(s,depth))
            self.assertEqual(screen(s,depth)['engineering_approval'],'BLOCKED/NO-GO')
    def test_contract_and_hazards(self):
        c=json.loads((ROOT/'contracts/geotechnical_interface.json').read_text())
        self.assertEqual(c['authorization'],'none')
        h=json.loads((ROOT/'safety/hazards.json').read_text())
        self.assertEqual(len([x for x in h['hazards'] if x['id'].startswith('ISLAND-GEO-HZ-')]),5)
    def test_requirements_trace(self):
        r=json.loads((ROOT/'models/requirements.json').read_text())['requirements']
        self.assertEqual(len([x for x in r if not x['id'].startswith(('ISLAND-GEO2-', 'ISLAND-GEO-004-', 'ISLAND-GEO-005-', 'ISLAND-GEO-006-', 'ISLAND-GEO-007-', 'ISLAND-GEO-008-', 'ISLAND-GEO-009-', 'ISLAND-GEO-010-', 'ISLAND-GEO-011-', 'ISLAND-GEO-012-', 'ISLAND-GEO-013-', 'ISLAND-GEO-014-', 'ISLAND-GEO-015-', 'ISLAND-GEO-016-', 'ISLAND-GEO-017-', 'ISLAND-GEO-018-', 'ISLAND-GEO-020-', 'ISLAND-GEO-021-', 'ISLAND-GEO-022-'))]),21)
        self.assertEqual(len({x['id'] for x in r}),len(r))

if __name__=='__main__': unittest.main()
