# Stage 142 — Ambiguous Authorization Acknowledgement and Competing Consumers

Adds an integration test for a retry authorization whose SQLite transaction is
committed durably but whose COMMIT acknowledgement is lost. Two independent
processes then race to consume that one-shot authorization.

Assertions: the store resolves the ambiguous commit from the durable row; exactly
one consumer starts the retry and the other is blocked; attempt count and fencing
token advance exactly once from 1 to 2; the replacement owner UUID differs from
the initial owner; consumed authorization metadata is cleared and another start is
blocked.

No production code changes are made. This covers local SQLite transaction
behavior and is not a claim of distributed or railway safety certification.
