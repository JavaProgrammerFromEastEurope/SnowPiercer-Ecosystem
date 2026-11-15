# Evidence scope
Three full unittest discovery runs use Python warning filters as errors and save stdout/stderr, return code and counts. This is a local functional regression only. No cross-UID E2E or exhaustive SIGKILL matrix was executed. Any unsuccessful runs are preserved under evidence if present. Production status remains BLOCKED/NO-GO.
