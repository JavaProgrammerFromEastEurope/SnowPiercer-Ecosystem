from scripts.ci.minimize_order_failure import minimize

def test_order_preserved_and_reduced():
    assert minimize(['a','b','c','d'], lambda xs: 'b' in xs and 'd' in xs) == ['b','d']

def test_nonreproducing_sequence_remains_unmodified():
    assert minimize(['a','b'], lambda xs: False) == ['a','b']
