"""Run from the repository root with python3 -m serving_lab."""
import argparse
import http.client
import json
import math
import os
import sys
from pathlib import Path

from .client import check_server
from .runtime import doctor, load_environment, run_experiment, save_json


def parser():
    result = argparse.ArgumentParser(description='A small LLM-serving experiment toolkit.')
    commands = result.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Print non-identifying machine and Python metadata.')
    server = commands.add_parser('check-server', help='Check a server and list its model IDs.')
    server.add_argument('--base-url', default='http://127.0.0.1:8080')
    server.add_argument('--timeout', type=float, default=10.0)
    for name in ('capture', 'sweep'):
        command = commands.add_parser(name, help='Capture one experiment.' if name == 'capture'
                                       else 'Compare a bounded list of concurrency levels.')
        command.add_argument('--base-url', default='http://127.0.0.1:8080')
        command.add_argument('--model', required=True)
        command.add_argument('--prompt-file', type=Path, required=True)
        command.add_argument('--environment', type=Path)
        command.add_argument('--max-tokens', type=int, default=64)
        command.add_argument('--temperature', type=float, default=0.0)
        command.add_argument('--seed', type=int, default=42)
        command.add_argument('--timeout', type=float, default=120.0)
        command.add_argument('--requests', type=int, default=1 if name == 'capture' else 8)
        command.add_argument('--concurrency', default='1' if name == 'capture' else '1,2,4')
        command.add_argument('--name', default='baseline' if name == 'capture' else 'concurrency')
        command.add_argument('--output', type=Path, required=True,
                             help='New JSON file.' if name == 'capture' else 'New output directory.')
        command.add_argument('--fixture', action='store_true',
                             help='Explicitly label synthetic/mock evidence; never counts as a live model.')
    validate = commands.add_parser('validate', help='Check evidence structure, not exact model text.')
    validate.add_argument('files', nargs='+', type=Path)
    validate.add_argument('--require-live', action='store_true')
    validate.add_argument('--require-success', action='store_true',
                          help='Require every request to finish successfully with visible text.')
    summary = commands.add_parser('summarize', help='Summarize recorded measurements.')
    summary.add_argument('files', nargs='+', type=Path)
    summary.add_argument('--output', type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'doctor':
            print(json.dumps(doctor(), indent=2))
            return 0
        if args.command == 'check-server':
            if not math.isfinite(args.timeout) or not 0 < args.timeout <= 3600:
                raise ValueError('Timeout must be finite and between 0 and 3600 seconds.')
            print(json.dumps(check_server(args.base_url, args.timeout,
                                          os.environ.get('LAB_API_KEY')), indent=2))
            return 0
        if args.command == 'validate':
            from .validation import validate_artifact
            valid = True
            for path in args.files:
                report = validate_artifact(json.loads(path.read_text(encoding='utf-8')),
                                           require_live=args.require_live,
                                           require_success=args.require_success)
                print(json.dumps({'file': str(path), **report}, indent=2))
                valid = valid and report['valid']
            return 0 if valid else 1
        if args.command == 'summarize':
            from .summary import summarize_artifacts
            artifacts = [json.loads(path.read_text(encoding='utf-8')) for path in args.files]
            text = summarize_artifacts(artifacts)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open('x', encoding='utf-8') as handle:
                    handle.write(text)
                print('Wrote ' + str(args.output))
            else:
                print(text)
            return 0
        concurrency = [int(part.strip()) for part in args.concurrency.split(',')]
        if args.command == 'capture' and len(concurrency) != 1:
            raise ValueError('Capture accepts one concurrency level; use sweep for a list.')
        if len(set(concurrency)) != len(concurrency):
            raise ValueError('Concurrency levels must be distinct.')
        if not 1 <= args.requests <= 10000 or any(
                c < 1 or c > min(args.requests, 64) for c in concurrency):
            raise ValueError('Use 1–10000 requests and concurrency between 1 and min(requests, 64).')
        if args.output.exists():
            raise FileExistsError('Output already exists; choose a new experiment path.')
        environment = load_environment(args.environment)
        prompt = args.prompt_file.read_text(encoding='utf-8')
        if args.command == 'sweep':
            args.output.mkdir(parents=True, exist_ok=False)
        failed = False
        for level in concurrency:
            artifact = run_experiment(args.base_url, args.model, prompt, args.requests,
                level, args.max_tokens, args.temperature, args.seed, args.timeout,
                environment, args.name, os.environ.get('LAB_API_KEY'), args.fixture)
            output = args.output if args.command == 'capture' else args.output / (
                'concurrency-%s.json' % level)
            save_json(output, artifact)
            errors = sum(r['status'] != 'ok' for r in artifact['requests'])
            failed = failed or errors > 0
            print('Wrote %s (%s; %s requests; %s errors)' % (
                output, artifact['mode'], len(artifact['requests']), errors))
        return 2 if failed else 0
    except (OSError, ValueError, TypeError, http.client.HTTPException) as exc:
        # HTTPError/URLError strings may contain an arbitrary remote URL/body.
        from urllib.error import URLError
        message = 'Unable to read the configured server.' if isinstance(exc, URLError) else str(exc)
        print('Error: ' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
