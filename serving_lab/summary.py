"""Descriptive summaries; no claims of deterministic text or performance."""
import csv
import io
import json
import math
import statistics

from .validation import validate_artifact


def percentile(values, percent):
    """Empirical nearest-rank percentile, without interpolation."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(percent / 100 * len(ordered)) - 1))]


def _median(values):
    return statistics.median(values) if values else None


def _policy(provenance, term):
    values = {key: value for key, value in provenance.items() if isinstance(key, str) and term in key.lower()}
    return json.dumps(values, sort_keys=True, ensure_ascii=False) if values else 'unrecorded'


def summary_rows(artifacts):
    """One row per run. Never pool different conditions or hardware."""
    rows = []
    for artifact in artifacts:
        result = validate_artifact(artifact)
        if not result['valid']:
            raise ValueError('Invalid artifact cannot be summarized: ' + '; '.join(result['errors']))
        requests = artifact['requests']
        successful = [request for request in requests if request['status'] == 'ok']
        first = [request['time_to_first_content_ms'] for request in successful
                 if request['time_to_first_content_ms'] is not None]
        elapsed = [request['elapsed_ms'] for request in successful]
        usage = [request.get('usage') for request in requests]
        complete_usage = bool(requests) and all(isinstance(item, dict) and type(item.get('completion_tokens')) is int
                                               for item in usage)
        tokens = sum(item['completion_tokens'] for item in usage) if complete_usage else None
        seconds = artifact['duration_ms'] / 1000
        throughput = tokens / seconds if tokens is not None and seconds > 0 else None
        experiment = artifact['experiment']
        provenance = artifact['environment']['provenance']
        rows.append({
            'run_id': artifact['run_id'],
            'mode': artifact['mode'],
            'experiment': experiment['name'],
            'model': artifact['server']['model'],
            'concurrency': experiment['concurrency'],
            'requests': len(requests),
            'successful': len(successful),
            'errors': len(requests) - len(successful),
            'first_content_samples': len(first),
            'first_content_p50_ms': _median(first),
            'first_content_p95_ms': percentile(first, 95),
            'elapsed_p50_ms': _median(elapsed),
            'elapsed_p95_ms': percentile(elapsed, 95),
            'wall_time_ms': artifact['duration_ms'],
            'completion_tokens_total': tokens,
            'output_tokens_per_second': throughput,
            'cache_policy': _policy(provenance, 'cache'),
            'warmup_policy': _policy(provenance, 'warm'),
            'provenance_json': json.dumps(provenance, sort_keys=True, ensure_ascii=False),
        })
    return rows


def comparison_notes(artifacts):
    """Flag recorded confounds; absence of a warning is not causal proof."""
    if len(artifacts) < 2:
        return ['Only one run is present; collect repeated runs before making comparative claims.']
    dimensions = {
        'mode (live versus fixture)': [item['mode'] for item in artifacts],
        'model identifier': [item['server']['model'] for item in artifacts],
        'prompt': [item['experiment']['prompt_sha256'] for item in artifacts],
        'output limit': [item['experiment']['max_tokens'] for item in artifacts],
        'temperature': [item['experiment']['temperature'] for item in artifacts],
        'seed': [item['experiment']['seed'] for item in artifacts],
        'request count': [item['experiment']['request_count'] for item in artifacts],
        'provenance (including warmup/cache policies)': [item['environment']['provenance'] for item in artifacts],
        'recording platform': [(item['environment']['system'], item['environment']['machine']) for item in artifacts],
    }
    changed = [name for name, values in dimensions.items()
               if len({json.dumps(value, sort_keys=True) for value in values}) > 1]
    notes = []
    if changed:
        notes.append('Recorded conditions differ: ' + ', '.join(changed) +
                     '. Differences may be intentional, but do not attribute all observed change to concurrency.')
    notes.append('Runs remain separate. Cold/warmed runs, cache-reuse policies, models, and hardware are never pooled.')
    return notes


def _cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def _display(value):
    return '—' if value is None else ('%.2f' % value if isinstance(value, float) else str(value))


def summarize_artifacts(artifacts):
    """Return Markdown after validating every input artifact."""
    artifacts = list(artifacts)
    rows = summary_rows(artifacts)
    lines = [
        '# Serving experiment summary', '',
        'Each row is one recorded run. Latencies are milliseconds and use successful requests only. '
        'First-content timing is client-observed text arrival, not an exact model-token timestamp.', '',
        '| Run | Mode | Condition | Concurrency | Requests | OK / errors | First-content samples | First content p50 / p95 | Completion p50 / p95 | Output tokens/s |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for row in rows:
        values = [row['run_id'], row['mode'], row['experiment'], row['concurrency'], row['requests'],
                  '%s / %s' % (row['successful'], row['errors']), row['first_content_samples'],
                  '%s / %s' % (_display(row['first_content_p50_ms']), _display(row['first_content_p95_ms'])),
                  '%s / %s' % (_display(row['elapsed_p50_ms']), _display(row['elapsed_p95_ms'])),
                  _display(row['output_tokens_per_second'])]
        lines.append('| ' + ' | '.join(_cell(value) for value in values) + ' |')
    if not rows:
        lines += ['', 'No artifacts supplied.']
    lines += [
        '', '## How to interpret these measurements', '',
        '- p50 is the sample median; p95 uses nearest rank: sorted sample at ceil(0.95 × N). '
        'With fewer than 20 samples, p95 is the maximum. These are descriptive samples, not confidence bounds.',
        '- Output tokens/s = sum of server-reported completion tokens across all requests / whole-run wall time. '
        'It includes waiting and prompt processing. It is not the mean of per-request rates or a pure decode rate.',
        '- If any request lacks completion-token usage, throughput is unavailable (—). '
        'Text chunks, characters, and words are never substituted for model tokens. '
        'Server completion-token usage may include hidden reasoning, depending on the model/server.',
        '- Error records remain visible; inspect their causes. Successful-only latency can hide the cost of failures.',
        '- A fixed seed and temperature do not guarantee identical text or timings across machines, versions, or batching.',
    ]
    lines += ['- ' + note for note in comparison_notes(artifacts)]
    lines += ['', '## Recorded conditions and validation warnings', '']
    for artifact, row in zip(artifacts, rows):
        lines += ['### ' + _cell(row['run_id']), '',
                  '- Model: ' + _cell(row['model']),
                  '- Cache policy: ' + _cell(row['cache_policy']),
                  '- Warmup policy: ' + _cell(row['warmup_policy']),
                  '- Provenance: ' + _cell(row['provenance_json'])]
        lines += ['- ' + warning for warning in validate_artifact(artifact)['warnings']]
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def summary_csv(artifacts):
    """Return CSV with empty cells for unavailable measurements."""
    rows = summary_rows(list(artifacts))
    fields = ['run_id', 'mode', 'experiment', 'model', 'concurrency', 'requests', 'successful', 'errors',
              'first_content_samples', 'first_content_p50_ms', 'first_content_p95_ms', 'elapsed_p50_ms',
              'elapsed_p95_ms', 'wall_time_ms', 'completion_tokens_total', 'output_tokens_per_second',
              'cache_policy', 'warmup_policy', 'provenance_json']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()
