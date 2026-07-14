#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r'^[a-f0-9]{64}$')
ENVELOPE_ID = re.compile(r'^ev_[A-Za-z0-9_-]+$')
SOURCE_CLASSES = {
    'primary_official_record',
    'official_statement',
    'independent_technical',
    'reputable_reporting',
    'public_submission',
}


def stable_json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def fail(message):
    raise SystemExit(message)


def require(condition, message):
    if not condition:
        fail(message)


def validate_envelope(envelope):
    require(isinstance(envelope, dict), 'envelope must be an object')
    require(ENVELOPE_ID.fullmatch(envelope.get('id', '')), 'invalid envelope id')
    require(HEX64.fullmatch(envelope.get('artifact_sha256', '')), 'invalid envelope artifact_sha256')
    require(isinstance(envelope.get('retrieved_at'), str) and envelope['retrieved_at'], 'missing envelope retrieved_at')
    source = envelope.get('source')
    require(isinstance(source, dict), 'missing envelope source')
    require(isinstance(source.get('url'), str) and source['url'].startswith(('https://', 'http://')), 'invalid envelope source url')
    require(isinstance(source.get('publisher'), str) and source['publisher'], 'missing envelope source publisher')
    require(source.get('source_class') in SOURCE_CLASSES, 'invalid envelope source_class')
    derivation = envelope.get('derivation')
    require(isinstance(derivation, dict), 'missing envelope derivation')
    require(derivation.get('kind') in {'original', 'snapshot', 'ocr', 'extraction', 'redaction', 'translation'}, 'invalid derivation kind')
    require(isinstance(derivation.get('tool'), str) and derivation['tool'], 'missing derivation tool')
    require(isinstance(derivation.get('version'), str) and derivation['version'], 'missing derivation version')
    anchors = envelope.get('anchors')
    require(isinstance(anchors, list) and anchors, 'missing anchors')
    for anchor in anchors:
        require(isinstance(anchor, dict), 'anchor must be an object')
        require(isinstance(anchor.get('page'), int) and anchor['page'] >= 1, 'invalid anchor page')
        require(isinstance(anchor.get('text'), str) and anchor['text'], 'invalid anchor text')


def main():
    if len(sys.argv) != 2:
        fail('usage: verify_capsule.py <capsule.json>')
    path = Path(sys.argv[1])
    capsule = json.loads(path.read_text())
    require(capsule.get('kind') == 'project_xray_public_dossier_capsule', 'invalid capsule kind')
    require(capsule.get('schema_version') == '1', 'invalid capsule schema version')
    require(isinstance(capsule.get('project'), dict), 'missing project')
    require(isinstance(capsule.get('claims'), list), 'missing claims')
    require(isinstance(capsule.get('gaps'), list), 'missing gaps')
    require(isinstance(capsule.get('responses'), list), 'missing responses')
    envelopes = capsule.get('evidence_envelopes')
    require(isinstance(envelopes, list) and envelopes, 'missing evidence envelopes')
    for envelope in envelopes:
        validate_envelope(envelope)
    digest = capsule.get('capsule_sha256', '')
    require(HEX64.fullmatch(digest), 'invalid capsule_sha256')
    payload = dict(capsule)
    payload.pop('capsule_sha256', None)
    expected = hashlib.sha256(stable_json_bytes(payload)).hexdigest()
    require(expected == digest, 'capsule digest mismatch')
    print(json.dumps({'status': 'ok', 'capsule_sha256': digest, 'claims': len(capsule['claims']), 'evidence_envelopes': len(envelopes)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
