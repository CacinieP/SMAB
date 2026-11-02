"""Verify this evidence snapshot and its source checkout using Python stdlib."""
from pathlib import Path
from datetime import datetime
import gzip
import hashlib
import json
import re

DEST = Path(__file__).resolve().parent
REPO = DEST.parents[2]
SOURCE = DEST


def main():
    frozen = json.loads((DEST/'prompt-freeze.json').read_text())
    assert hashlib.sha256((DEST/'prompts/optimized.txt').read_bytes()).hexdigest() == frozen['sha256']
    entries = json.loads((DEST/'artifact-index.json').read_text())
    attempts = 0
    benchmark_files = 0
    cases = set()
    confirmation_files = 0
    for entry in entries:
        packed = (DEST/entry['file']).read_bytes()
        raw = gzip.decompress(packed)
        assert hashlib.sha256(packed).hexdigest() == entry['compressed_sha256']
        assert hashlib.sha256(raw).hexdigest() == entry['uncompressed_sha256']
        assert len(raw) == entry['uncompressed_bytes']
        data = json.loads(raw)
        if 'suite' not in data:
            continue
        benchmark_files += 1
        assert data['suite']['repeats'] == 3
        assert data['suite']['case_count'] in [11, 13, 17]
        for run in data['runs']:
            assert run['run']['case_count'] == len(run['results']) == data['suite']['case_count']
            attempts += len(run['results'])
            cases.update(result['id'] for result in run['results'])
        if entry['file'].startswith('confirmation/'):
            confirmation_files += 1
            assert datetime.fromisoformat(data['runs'][0]['run']['started_at']) > datetime.fromisoformat(frozen['frozen_at_utc'])
            if '-optimized-' in entry['file']:
                for run in data['runs']:
                    assert hashlib.sha256(run['run']['system_prompt'].encode()).hexdigest() == frozen['sha256']
    assert benchmark_files == 52, benchmark_files
    assert confirmation_files == 20, confirmation_files
    assert attempts == 2316, attempts
    assert len(cases) == 41, len(cases)
    manifest = json.loads((DEST/'experiment-manifest.json').read_text())
    for name, digest in manifest['files_sha256'].items():
        assert hashlib.sha256((REPO/name).read_bytes()).hexdigest() == digest, name
    broken = []
    for file in [REPO/'docs/GEMMA4.md', DEST/'README.md']:
        for target in re.findall(r'\]\(([^)]+)\)', file.read_text()):
            if '://' not in target and not target.startswith('#') and not (file.parent/target.split('#')[0]).exists():
                broken.append((str(file.relative_to(REPO)), target))
    assert not broken, broken
    result = {'status':'PASS','benchmark_files':benchmark_files,'confirmation_files':confirmation_files,
              'raw_artifacts':len(entries),'episode_attempts':attempts,'distinct_cases':len(cases),
              'checks':['compressed and raw SHA256','all expected runs and repetitions','frozen prompt unchanged',
                        'confirmation starts after freeze','dataset and core source hashes unchanged','report links exist']}
    (SOURCE/'verification-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
