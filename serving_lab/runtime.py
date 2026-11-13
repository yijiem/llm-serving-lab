"""Experiment orchestration and intentionally limited public metadata."""
import hashlib
import json
import math
import os
import platform
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .client import normalize_base_url, stream_request, utcnow

PROVENANCE_KEYS = frozenset(('engine', 'engine_version', 'model_artifact',
    'model_sha256', 'quantization', 'backend', 'context_size', 'parallel_slots',
    'cache_policy', 'warmup_policy', 'hardware', 'notes'))


def doctor():
    return {'system': platform.system(), 'machine': platform.machine(),
            'python_version': platform.python_version(), 'cpu_count': os.cpu_count()}


def load_environment(path=None):
    provenance = json.loads(Path(path).read_text(encoding='utf-8')) if path else {}
    if not isinstance(provenance, dict):
        raise ValueError('Environment file must contain a JSON object.')
    unknown = sorted(set(provenance) - PROVENANCE_KEYS)
    if unknown:
        raise ValueError('Environment file contains unsupported fields: ' + ', '.join(unknown))
    for key, value in provenance.items():
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError('Environment values must be scalar: ' + key)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Environment values must be finite: ' + key)
    result = doctor()
    result['provenance'] = provenance
    return result


def save_json(path, artifact):
    """Exclusive create: a repeated command never replaces earlier evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with path.open('x', encoding='utf-8') as handle:
        handle.write(text)


def run_experiment(base_url, model, prompt, request_count=1, concurrency=1,
                   max_tokens=64, temperature=0.0, seed=42, timeout=120.0,
                   environment=None, name='baseline', api_key=None, fixture=False):
    if not 1 <= request_count <= 10000:
        raise ValueError('Request count must be between 1 and 10000.')
    if not 1 <= concurrency <= 64 or concurrency > request_count:
        raise ValueError('Concurrency must be between 1 and min(request count, 64).')
    if not 1 <= max_tokens <= 32768:
        raise ValueError('Max tokens must be between 1 and 32768.')
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError('Temperature must be finite and between 0 and 2.')
    if not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError('Timeout must be finite and between 0 and 3600 seconds.')
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('Prompt must contain text.')
    if len(prompt.encode('utf-8')) > 1024 * 1024:
        raise ValueError('Prompt exceeds the 1 MiB input limit.')
    if not isinstance(model, str) or not model.strip():
        raise ValueError('Model ID must contain text.')
    base_url = normalize_base_url(base_url)
    artifact = {
        'schema_version': 1, 'run_id': str(uuid.uuid4()), 'created_at_utc': utcnow(),
        'mode': 'fixture' if fixture else 'live',
        'environment': environment if environment is not None else load_environment(),
        'server': {'base_url': base_url, 'model': model},
        'experiment': {'name': name, 'prompt': prompt,
            'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
            'request_count': request_count, 'concurrency': concurrency,
            'max_tokens': max_tokens, 'temperature': temperature, 'seed': seed,
            'timeout_seconds': timeout},
        'duration_ms': 0.0, 'requests': [],
    }
    def perform(index):
        return stream_request(base_url, model, prompt, index, max_tokens,
                              temperature, seed, timeout, api_key, fixture)
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        artifact['requests'] = list(executor.map(perform, range(request_count)))
    artifact['duration_ms'] = round((time.perf_counter() - start) * 1000, 6)
    if any(request['fixture'] for request in artifact['requests']):
        artifact['mode'] = 'fixture'
    return artifact
