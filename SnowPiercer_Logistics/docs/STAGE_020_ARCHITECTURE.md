# Architecture

Stage 020 adds an opt-in MandatoryProductionLogisticsService subclass and a ProductionIdentityPolicy. No inherited public API is removed. The production start method fails closed *before* socket publication. A deterministic crash_state_matrix enumerates six modeled states; it is not a physical crash injection matrix. Existing stage015 direct client attestation, witness CAS and SQLite ledger components remain separate and have not been integrated into a four-UID production transaction. Independent production admission is withheld.
