# LOG-CORE-010 contracts
IsolationPolicy(service_uid:int,witness_uid:int,authority_uid:int,client_uids:tuple).validate() -> True or AdmissionError.
require_private_directory(path,owner_uid) -> True or AdmissionError.
verify_isolated_deployment(policy,service_root,witness_root,authority_root) -> True or AdmissionError.
IsolatedLogisticsService(...,isolation_policy,witness_root,authority_root) is opt-in; inherited public APIs unchanged. Failure to pass preflight is fail-closed; successful preflight is NOT a security certification.
