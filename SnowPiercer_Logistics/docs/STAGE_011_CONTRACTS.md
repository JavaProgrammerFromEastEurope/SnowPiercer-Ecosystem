# Contracts
`verify_deployment(layout, require_sockets=True) -> True | raises AdmissionError`; no creation, chmod or chown. `verify_legacy_denied(root, service_uid=...) -> True | raises AdmissionError` only when run as non-root non-service UID. Caller must arrange privileged identity provisioning. Stage010 APIs remain unchanged. There is no independent client identity attestation in Stage011.
