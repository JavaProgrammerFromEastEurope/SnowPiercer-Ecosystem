import unittest
from railsystem.contracts import AuthorityStatus, MovementAuthority

class ContractTests(unittest.TestCase):
    def test_unknown_denies(self):
        self.assertFalse(MovementAuthority("T1", AuthorityStatus.UNKNOWN).simulation_permitted)

    def test_grant_without_issuer_denies(self):
        self.assertFalse(MovementAuthority("T1", AuthorityStatus.GRANTED).simulation_permitted)

    def test_grant_with_issuer(self):
        self.assertTrue(MovementAuthority("T1", AuthorityStatus.GRANTED, "simulator").simulation_permitted)

    def test_invalid_status(self):
        with self.assertRaises(TypeError):
            MovementAuthority("T1", "granted")

if __name__ == "__main__":
    unittest.main()
