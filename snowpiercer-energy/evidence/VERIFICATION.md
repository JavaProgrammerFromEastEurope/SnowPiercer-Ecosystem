# Verification record

Three full available test-suite runs use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning`. The initial three attempts without disabling third-party plugin autoload failed during pytest configuration due to an external pytest-asyncio deprecation warning. Those failed attempts were superseded by clean runs; disabling plugin autoload is documented as an environmental limitation, not evidence of plugin compatibility. See regression-1.txt through regression-3.txt for final results.

Scope: unit tests of simulation-only domain. Not hardware-in-the-loop, independent verification, performance or physical safety evidence. Decision: NO-GO.
