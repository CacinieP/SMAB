"""Re-run a recorded profile into a fresh directory, from an installed SMAB checkout.

Start the matching Ollama service and install the recorded weights first. This
script never downloads models and never changes the benchmark dataset or scorer.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VARIANTS = [('original', 0), ('shuffled', 0), ('shuffled', 42), ('aliased', 0)]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--model', required=True, choices=['e4b', 'e2b'])
    parser.add_argument('--phase', required=True, choices=['baseline', 'optimized-core', 'confirmation', 'thinking-diagnostic'])
    parser.add_argument('--base-url', default='http://127.0.0.1:11435/v1')
    parser.add_argument('--output-dir', type=Path, default=REPO/'reproduced/gemma4-2026-11-02')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    stages = []
    if args.phase == 'baseline':
        stages = [('core', schema, seed, False, 'native') for schema, seed in VARIANTS]
        stages += [('core', 'original', 0, False, 'json')]
    elif args.phase == 'optimized-core':
        stages = [('core', schema, seed, True, 'native') for schema, seed in VARIANTS]
    elif args.phase == 'thinking-diagnostic':
        stages = [('core', 'original', 0, False, 'native')]
    else:
        stages = [('ood', schema, seed, optimized, 'native') for schema, seed in VARIANTS for optimized in [False, True]]
        stages += [('supplementary', 'original', 0, optimized, 'native') for optimized in [False, True]]
    prompt = HERE/'prompts/optimized.txt'
    if any(stage[3] for stage in stages):
        frozen = json.loads((HERE/'prompt-freeze.json').read_text())
        if hashlib.sha256(prompt.read_bytes()).hexdigest() != frozen['sha256']:
            raise SystemExit('Frozen prompt hash mismatch')
    for split, schema, seed, optimized, channel in stages:
        name = f'{args.model}-{channel}-{schema}-seed{seed}-{split}-{args.phase}'
        if args.phase == 'confirmation':
            name += '-optimized' if optimized else '-default'
        output = args.output_dir/f'{name}.json'
        command = ['smab', 'run', '--dataset', str(REPO/'datasets'/('minicpm47_extra.jsonl' if split == 'supplementary' else 'core.jsonl')),
                   '--tools', str(REPO/'datasets/tools.json'), '--model', f'gemma4:{args.model}',
                   '--base-url', args.base_url, '--api-key-env', 'SMAB_LOCAL_UNUSED_KEY',
                   '--tool-format', channel, '--schema-variant', schema, '--seed', str(seed),
                   '--temperature', '0', '--max-tokens', '512', '--timeout', '60', '--repeats', '3',
                   '--extra-body', json.dumps({'seed': 0} if args.phase == 'thinking-diagnostic' else {'reasoning_effort': 'none', 'seed': 0}),
                   '--output', str(output), '--report', str(output.with_suffix('.md'))]
        if split != 'supplementary':
            command += ['--split', split]
        if optimized:
            command += ['--system-prompt-file', str(prompt)]
        print(shlex.join(command), flush=True)
        if not args.dry_run:
            if output.exists():
                raise SystemExit(f'Refusing to overwrite {output}')
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
