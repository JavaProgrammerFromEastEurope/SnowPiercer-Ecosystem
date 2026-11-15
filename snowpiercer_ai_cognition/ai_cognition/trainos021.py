"""AI-CORE-021: context-bound, expiring recommendations for TrainOS review.

This opt-in library bridge has no actuation or operator-approval operation.
The output HMAC key and current TrainOS context must come from trusted local
configuration. It is not a substitute for deployment isolation or a trusted clock.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import math
import threading
import time
from typing import Mapping
import uuid

from .admission import TrustedAdmission
from .core import Decision, Recommendation, assess
from .gateway import MandatoryAdmissionGateway
from .production014 import JournaledAdmissionGateway

SCHEMA = 'snowpiercer.ai.trainos.proposal.v1'
MAX_PROPOSAL_BYTES = 8192
_CONTEXT_FIELDS = {'context_id', 'revision', 'observed_at', 'state_sha256'}
_BODY_FIELDS = {'schema', 'proposal_id', 'source', 'target', 'event_id', 'decision',
                'reason_code', 'evidence_sha256', 'context', 'issued_at', 'expires_at',
                'actionable', 'operator_review_required'}
_DECISION_REASONS = {'OBSERVE': 'SEVERITY_INFO', 'INVESTIGATE': 'SEVERITY_WARNING',
                     'ESCALATE': 'SEVERITY_CRITICAL'}


class ProposalRejected(ValueError):
    """Fail-closed rejection with a stable, non-sensitive reason code."""


def _bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ProposalRejected('INVALID_PROPOSAL') from exc


def _identifier(value):
    return (isinstance(value, str) and 1 <= len(value) <= 128 and value.isascii()
            and all(c.isalnum() or c in '-_.' for c in value))


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _timestamp(value):
    return type(value) is int and 0 <= value <= 253402300799


def _context(value):
    if not isinstance(value, Mapping) or set(value) != _CONTEXT_FIELDS:
        raise ProposalRejected('INVALID_CONTEXT')
    if (not _identifier(value['context_id']) or type(value['revision']) is not int
            or value['revision'] < 0 or not _timestamp(value['observed_at'])
            or not _digest(value['state_sha256'])):
        raise ProposalRejected('INVALID_CONTEXT')
    return dict(value)


@dataclass(frozen=True)
class ReviewRecommendation:
    proposal_id: str
    event_id: str
    decision: Decision
    reason_code: str
    evidence_sha256: str
    context_id: str
    context_revision: int
    context_sha256: str
    issued_at: int
    expires_at: int
    actionable: bool = field(default=False, init=False)
    operator_review_required: bool = field(default=True, init=False)


class TrainOSRecommendationBridge:
    """Issue authenticated review proposals only after trusted observation admission.

    ``current_context`` is supplied by TrainOS, not an untrusted model. A proposal
    may be reviewed repeatedly; this is deliberately not an execution/replay API.
    """
    def __init__(self, admission, proposal_key, *, clock=None, proposal_ttl=30,
                 max_context_age=120):
        if not isinstance(admission, (TrustedAdmission, MandatoryAdmissionGateway,
                                      JournaledAdmissionGateway)):
            raise TypeError('TRUSTED_ADMISSION_REQUIRED')
        if not isinstance(proposal_key, bytes) or len(proposal_key) < 32:
            raise ValueError('proposal_key must contain at least 32 bytes')
        if type(proposal_ttl) is not int or not 1 <= proposal_ttl <= 300:
            raise ValueError('proposal_ttl must be an integer from 1 to 300')
        if type(max_context_age) is not int or not 1 <= max_context_age <= 3600:
            raise ValueError('max_context_age must be an integer from 1 to 3600')
        self._admission = admission
        self._key = proposal_key
        self._clock = clock if clock is not None else time.time
        self._ttl = proposal_ttl
        self._context_age = max_context_age
        # Process-local rollback fence, shared by issuance and every review
        # attempt (including rejected inputs). A new bridge starts a new fence;
        # persistence and cross-process trusted time remain deployment concerns.
        self._clock_lock = threading.Lock()
        self._clock_high_watermark = None

    def _now(self):
        with self._clock_lock:
            try:
                value = self._clock()
            except Exception as exc:
                raise ProposalRejected('CLOCK_UNAVAILABLE') from exc
            if (type(value) not in (int, float) or not 0 <= value < 253402300799
                    or not math.isfinite(value)):
                raise ProposalRejected('CLOCK_UNAVAILABLE')
            if self._clock_high_watermark is not None and value < self._clock_high_watermark:
                raise ProposalRejected('CLOCK_MOVED_BACKWARDS')
            # Keep the original precision so a fractional rollback is not hidden
            # by the integer timestamps in the wire format.
            self._clock_high_watermark = value
            return int(value)

    def _fresh_context(self, value, now):
        context = _context(value)
        if context['observed_at'] > now:
            raise ProposalRejected('FUTURE_CONTEXT')
        # Expiry is exclusive: context cannot produce a proposal with zero life.
        if now >= context['observed_at'] + self._context_age:
            raise ProposalRejected('STALE_CONTEXT')
        return context

    def issue(self, envelope, current_context):
        """Consume one observation admission and return a signed review-only dict.

        Invalid/stale context is rejected before the replay reservation. If time
        passes during successful admission, no proposal is released for stale
        context, but the observation remains consumed by its original gateway.
        """
        started = self._now()
        context = self._fresh_context(current_context, started)
        raw = _bytes(envelope)
        if len(raw) > MAX_PROPOSAL_BYTES:
            raise ProposalRejected('OVERSIZED_ENVELOPE')
        snapshot = json.loads(raw)
        result = self._admission.admit(snapshot)
        if not isinstance(result, Recommendation) or result.actionable is not False:
            raise ProposalRejected('NON_REVIEW_RECOMMENDATION')
        expected = assess(snapshot['observation'])
        if result != expected:
            raise ProposalRejected('RECOMMENDATION_EVIDENCE_MISMATCH')
        now = self._now()
        if now < started:
            raise ProposalRejected('CLOCK_MOVED_BACKWARDS')
        self._fresh_context(context, now)
        body = {'schema': SCHEMA, 'proposal_id': uuid.uuid4().hex,
                'source': 'AI/Cognition', 'target': 'TrainOS',
                'event_id': result.event_id, 'decision': result.decision.value,
                'reason_code': result.reason_code, 'evidence_sha256': result.evidence_sha256,
                'context': context, 'issued_at': now,
                'expires_at': min(now + self._ttl, context['observed_at'] + self._context_age,
                                  253402300799),
                'actionable': False, 'operator_review_required': True}
        return dict(body, mac=hmac.new(self._key, _bytes(body), hashlib.sha256).hexdigest())

    def verify_for_review(self, proposal, current_context):
        """Verify provenance, immutable non-actionability, current context and expiry."""
        # Observe time even for malformed/authentication-failed input. Otherwise
        # an invalid call could conceal an observed expired/stale clock sample.
        self._now()
        if not isinstance(proposal, Mapping):
            raise ProposalRejected('INVALID_PROPOSAL')
        raw = _bytes(proposal)
        if len(raw) > MAX_PROPOSAL_BYTES:
            raise ProposalRejected('OVERSIZED_PROPOSAL')
        snapshot = json.loads(raw)
        if set(snapshot) != _BODY_FIELDS | {'mac'} or not _digest(snapshot['mac']):
            raise ProposalRejected('INVALID_PROPOSAL')
        body = {k: snapshot[k] for k in _BODY_FIELDS}
        expected_mac = hmac.new(self._key, _bytes(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(snapshot['mac'], expected_mac):
            raise ProposalRejected('PROPOSAL_AUTHENTICATION_FAILED')
        if (body['schema'] != SCHEMA or body['source'] != 'AI/Cognition'
                or body['target'] != 'TrainOS' or not _identifier(body['proposal_id'])
                or not _identifier(body['event_id']) or not _digest(body['evidence_sha256'])
                or not isinstance(body['decision'], str)
                or body['decision'] not in _DECISION_REASONS
                or body['reason_code'] != _DECISION_REASONS[body['decision']]
                or body['actionable'] is not False or body['operator_review_required'] is not True
                or not _timestamp(body['issued_at']) or not _timestamp(body['expires_at'])):
            raise ProposalRejected('INVALID_PROPOSAL')
        issued = body['issued_at']
        context = _context(body['context'])
        if not (context['observed_at'] <= issued < body['expires_at']
                <= min(issued + self._ttl, context['observed_at'] + self._context_age)):
            raise ProposalRejected('INVALID_PROPOSAL')
        now = self._now()
        if now < issued:
            raise ProposalRejected('PROPOSAL_FROM_FUTURE')
        if now >= body['expires_at']:
            raise ProposalRejected('PROPOSAL_EXPIRED')
        actual_context = self._fresh_context(current_context, now)
        if actual_context != context:
            raise ProposalRejected('CONTEXT_CHANGED')
        return ReviewRecommendation(body['proposal_id'], body['event_id'],
            Decision(body['decision']), body['reason_code'], body['evidence_sha256'],
            context['context_id'], context['revision'], context['state_sha256'],
            issued, body['expires_at'])
