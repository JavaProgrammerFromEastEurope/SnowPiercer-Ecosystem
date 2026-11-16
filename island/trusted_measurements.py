"""ISLAND-GEO-007: signed, semantically bound measurements; local replay ledger.
Not a certified instrument, independent CA, or rollback-proof trusted storage.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json, math, sqlite3
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .geotechnics import GeotechnicalInputError
from .provenance import ScenarioEvidence
from .consistency import assess_scenarios

UNITS = {'head':'m', 'conductivity':'m/s'}

def canonical(obj):
    """Canonical restricted JSON; no floats, duplicate keys, or implicit conversions."""
    def check(v):
        if v is None or type(v) in (str,bool,int): return
        if isinstance(v,list):
            for x in v: check(x)
            return
        if isinstance(v,dict) and all(type(k) is str for k in v):
            for x in v.values(): check(x)
            return
        raise GeotechnicalInputError('unsupported canonical value')
    check(obj)
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def parse_canonical(payload):
    if type(payload) is not bytes: raise GeotechnicalInputError('payload must be bytes')
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise GeotechnicalInputError('duplicate JSON key')
            out[k]=v
        return out
    try:
        obj=json.loads(payload.decode('utf-8'),object_pairs_hook=pairs,
                       parse_float=lambda _: (_ for _ in ()).throw(ValueError('float forbidden')),
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite forbidden')))
        if canonical(obj)!=payload: raise GeotechnicalInputError('noncanonical JSON')
        return obj
    except (ValueError,UnicodeError,TypeError,OverflowError) as e:
        raise GeotechnicalInputError('invalid canonical payload') from e

def _number(value):
    if type(value) is not str or not value or value.strip()!=value: raise GeotechnicalInputError('decimal string required')
    from decimal import Decimal, InvalidOperation
    try: d=Decimal(value)
    except InvalidOperation as e: raise GeotechnicalInputError('invalid decimal') from e
    if not d.is_finite() or len(value)>64: raise GeotechnicalInputError('invalid decimal')
    if value!=format(d,'f') or ('-' in value and d==0): raise GeotechnicalInputError('noncanonical decimal')
    return d

def _time(value):
    if type(value) is not str or not value.endswith('Z'): raise GeotechnicalInputError('UTC timestamp required')
    try: t=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as e: raise GeotechnicalInputError('invalid timestamp') from e
    if t.utcoffset().total_seconds()!=0 or t.isoformat(timespec='seconds').replace('+00:00','Z')!=value:
        raise GeotechnicalInputError('noncanonical UTC timestamp')
    return t

def validate_measurement(m):
    required={'source_id','source_version','observation_id','kind','unit','time_utc','low','high','sequence'}
    if type(m) is not dict or set(m)!=required: raise GeotechnicalInputError('measurement fields mismatch')
    if any(type(m[k]) is not str or not m[k] or m[k].strip()!=m[k] or len(m[k])>128 for k in ('source_id','observation_id')):
        raise GeotechnicalInputError('invalid identifiers')
    if type(m['source_version']) is not int or m['source_version']<1 or type(m['sequence']) is not int or m['sequence']<1:
        raise GeotechnicalInputError('invalid version or sequence')
    if m['kind'] not in UNITS or m['unit']!=UNITS[m['kind']]: raise GeotechnicalInputError('unit mismatch')
    _time(m['time_utc']); lo=_number(m['low']); hi=_number(m['high'])
    if lo>hi or (m['kind']=='conductivity' and lo<=0): raise GeotechnicalInputError('invalid measurement interval')
    return lo,hi

@dataclass(frozen=True)
class SignedMeasurement:
    payload: bytes
    signature: bytes
    def __post_init__(self):
        if type(self.payload) is not bytes or type(self.signature) is not bytes or len(self.signature)!=64:
            raise GeotechnicalInputError('invalid signed measurement')

@dataclass(frozen=True)
class TrustPolicy:
    """Root-pinned policy; root key must be provisioned out-of-band."""
    root_public_key: bytes
    policy_payload: bytes
    policy_signature: bytes
    def verified(self):
        if type(self.root_public_key) is not bytes or len(self.root_public_key)!=32 or type(self.policy_signature) is not bytes or len(self.policy_signature)!=64:
            raise GeotechnicalInputError('invalid root policy')
        try: Ed25519PublicKey.from_public_bytes(self.root_public_key).verify(self.policy_signature,b'ISLAND-POLICY-V1\x00'+self.policy_payload)
        except (InvalidSignature,ValueError) as e: raise GeotechnicalInputError('untrusted policy') from e
        obj=parse_canonical(self.policy_payload)
        if type(obj) is not dict or set(obj)!={'policy_version','sources'} or type(obj['policy_version']) is not int or obj['policy_version']<1 or type(obj['sources']) is not dict or not obj['sources']:
            raise GeotechnicalInputError('invalid policy structure')
        for sid,entry in obj['sources'].items():
            if type(sid) is not str or not sid or type(entry) is not dict or set(entry)!={'version','public_key'} or type(entry['version']) is not int or entry['version']<1 or type(entry['public_key']) is not str or len(entry['public_key'])!=64:
                raise GeotechnicalInputError('invalid source policy')
            try: Ed25519PublicKey.from_public_bytes(bytes.fromhex(entry['public_key']))
            except ValueError as e: raise GeotechnicalInputError('invalid source key') from e
        return obj

class ReplayLedger:
    """Atomic local replay guard. Local DB deletion/rollback is NOT detected."""
    def __init__(self,path):
        self.path=Path(path)
    def admit(self,items,policy_version):
        if not items: raise GeotechnicalInputError('empty ledger batch')
        db=sqlite3.connect(str(self.path),timeout=5,isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=5000')
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS observations (source TEXT NOT NULL, observation TEXT NOT NULL, sequence INTEGER NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(source,observation))')
            db.execute('CREATE TABLE IF NOT EXISTS heads (source TEXT PRIMARY KEY, sequence INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), policy_version INTEGER NOT NULL)')
            old=db.execute('SELECT policy_version FROM metadata WHERE id=1').fetchone()
            if old and policy_version<old[0]: raise GeotechnicalInputError('policy rollback')
            for m,digest in items:
                sid=m['source_id']; seq=m['sequence']; oid=m['observation_id']
                head=db.execute('SELECT sequence FROM heads WHERE source=?',(sid,)).fetchone()
                if head and seq<=head[0]: raise GeotechnicalInputError('replay or sequence rollback')
                if db.execute('SELECT 1 FROM observations WHERE source=? AND observation=?',(sid,oid)).fetchone():
                    raise GeotechnicalInputError('duplicate observation')
                db.execute('INSERT INTO observations VALUES (?,?,?,?)',(sid,oid,seq,digest))
                db.execute('INSERT INTO heads VALUES (?,?) ON CONFLICT(source) DO UPDATE SET sequence=excluded.sequence',(sid,seq))
            db.execute('INSERT INTO metadata VALUES (1,?) ON CONFLICT(id) DO UPDATE SET policy_version=excluded.policy_version',(policy_version,))
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction: db.execute('ROLLBACK')
            raise
        finally: db.close()

def admit_signed_measurements(scenario_evidence, signed, trust_policy, ledger, epoch_utc, critical_gradient=None):
    """Fail-closed admission; signed source data must exactly match model knots and conductivity."""
    reasons=set(); bound=[]
    try:
        if not isinstance(trust_policy,TrustPolicy) or not isinstance(ledger,ReplayLedger): raise GeotechnicalInputError('invalid trust inputs')
        policy=trust_policy.verified()
        epoch=_time(epoch_utc)
        if not isinstance(scenario_evidence,tuple) or not scenario_evidence or any(not isinstance(x,ScenarioEvidence) for x in scenario_evidence): raise GeotechnicalInputError('invalid scenarios')
        if type(signed) is not dict: raise GeotechnicalInputError('invalid signed mapping')
        expected={}
        for se in scenario_evidence:
            path=se.scenario.path
            for series in (path.upstream,path.downstream):
                for sample in series.samples:
                    expected[f'{series.boundary_id}@{sample.time_days}']=('head',sample.head_m,sample.time_days)
            expected[f'{path.path_id}@conductivity']=('conductivity',path.conductivity_m_s,None)
        records=[r for se in scenario_evidence for r in se.records]
        if len({r.evidence_id for r in records})!=len(records) or set(signed)!={r.evidence_id for r in records} or len({r.observation_id for r in records})!=len(records) or set(expected)!={r.observation_id for r in records}:
            raise GeotechnicalInputError('coverage or identifier mismatch')
        for r in records:
            item=signed[r.evidence_id]
            if not isinstance(item,SignedMeasurement): raise GeotechnicalInputError('invalid signed item')
            m=parse_canonical(item.payload); low,high=validate_measurement(m)
            if m['source_id']!=r.source_id or m['source_version']!=r.source_version or m['observation_id']!=r.observation_id or sha256(item.payload).hexdigest()!=r.payload_sha256:
                raise GeotechnicalInputError('evidence binding mismatch')
            entry=policy['sources'].get(r.source_id)
            if entry is None or entry['version']!=r.source_version: raise GeotechnicalInputError('source not trusted')
            try: Ed25519PublicKey.from_public_bytes(bytes.fromhex(entry['public_key'])).verify(item.signature,b'ISLAND-MEASUREMENT-V1\x00'+item.payload)
            except (InvalidSignature,ValueError) as e: raise GeotechnicalInputError('source signature invalid') from e
            kind,interval,time=expected[r.observation_id]
            if kind!=m['kind'] or interval is None: raise GeotechnicalInputError('missing or wrong measurement')
            from decimal import Decimal
            if low!=Decimal(str(interval.low)) or high!=Decimal(str(interval.high)):
                raise GeotechnicalInputError('numerical mismatch')
            if time is not None:
                expected_utc=(epoch+timedelta(days=time)).isoformat(timespec='seconds').replace('+00:00','Z')
                if m['time_utc']!=expected_utc: raise GeotechnicalInputError('timestamp does not bind to scenario time')
            elif m['time_utc']!=epoch_utc: raise GeotechnicalInputError('conductivity epoch mismatch')
            bound.append((m,sha256(item.payload).hexdigest()))
        model=assess_scenarios(tuple(se.scenario for se in scenario_evidence),critical_gradient)
        if not model['complete']: raise GeotechnicalInputError('incomplete numerical scenario')
        ledger.admit(bound,policy['policy_version'])
        return {'admitted':True,'reasons':[],'risk_flags':model['risk_flags'],
                'gradient':model['gradient'],'specific_discharge_m_s':model['specific_discharge_m_s'],
                'discharge_m3_s':model['discharge_m3_s'],'engineering_approval':'BLOCKED/NO-GO'}
    except (GeotechnicalInputError,sqlite3.Error,KeyError,TypeError,ValueError,OverflowError) as e:
        return {'admitted':False,'reasons':[type(e).__name__+': '+str(e)],'risk_flags':['MEASUREMENT_ADMISSION_DENIED','CONSERVATIVE_ESCALATION_REQUIRED'],
                'gradient':None,'specific_discharge_m_s':None,'discharge_m3_s':None,
                'engineering_approval':'BLOCKED/NO-GO'}
