# Architecture — Stage 013

`stage013.py` provides real kernel-UID subprocess probes using POSIX setgroups,
setgid, setuid; AF_UNIX SO_PEERCRED/getpeereid via existing `_peer_uid`;
and filesystem direct-open denial probes. The production entrypoint always refuses
admission. These are test harness capabilities, not a privileged daemon supervisor.

Trust boundaries: kernel UID is authenticated for each direct socket peer, but the
permit authority still trusts a service-reported original client UID. There is
no end-to-end independently verified client identity. Root and service UID can
access protected resources; inherited descriptors and mount namespace changes
are not covered by this harness.
