"""Check recorded evidence without requiring deterministic model answers.

These are consistency checks, not an attestation that an artifact is genuine.
Never infer model tokens from text chunks, characters, or words.
"""
import hashlib
import math
import re
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from uuid import UUID


def _number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_artifact(data, require_live=False, expected=None, require_success=False):
    """Return ``valid``, ``errors`` and ``warnings`` for one capture artifact.

    ``expected`` optionally supplies experiment field values, ``model`` or
    ``mode``. Matching these values checks a study's recorded configuration;
    it cannot establish that a server actually honored a sampling parameter.
    """
    errors, warnings = [], []

    def fail(path, message):
        errors.append(path + ': ' + message)

    def nonnegative(path, value, nullable=False):
        if nullable and value is None:
            return True
        if not _number(value) or value < 0:
            fail(path, 'must be a finite nonnegative number')
            return False
        return True

    def timestamp(path, value):
        try:
            if not isinstance(value, str):
                raise ValueError()
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            fail(path, 'must be an ISO-8601 UTC timestamp with a timezone')
            return None
        if parsed > datetime.now(timezone.utc) + timedelta(hours=24):
            warnings.append(path + ': over 24 hours in the future; check the recording clock')
        return parsed

    def identifier(path, value):
        try:
            if not isinstance(value, str):
                raise ValueError()
            UUID(value)
        except (ValueError, TypeError, AttributeError):
            fail(path, 'must be a UUID string')

    if not isinstance(data, dict):
        return {'valid': False, 'errors': ['artifact: must be an object'], 'warnings': []}
    if type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        fail('schema_version', 'must be 1')
    identifier('run_id', data.get('run_id'))
    created_at = timestamp('created_at_utc', data.get('created_at_utc'))
    mode = data.get('mode')
    if mode not in ('live', 'fixture'):
        fail('mode', 'must be live or fixture')
    elif mode == 'fixture':
        if require_live:
            fail('mode', 'fixture runs cannot satisfy --require-live')
        warnings.append('Fixture data verifies the measurement tools only; it is not a model benchmark.')
    if mode == 'live':
        warnings.append('The live label is recorded metadata, not independent proof of a real model run.')

    env = data.get('environment')
    if not isinstance(env, dict):
        fail('environment', 'must be an object')
        env = {}
    for field in ('system', 'machine', 'python_version'):
        if not isinstance(env.get(field), str) or not env.get(field):
            fail('environment.' + field, 'must be a nonempty string')
    cpu_count = env.get('cpu_count')
    if cpu_count is not None and (not _integer(cpu_count) or cpu_count < 1):
        fail('environment.cpu_count', 'must be a positive integer or null')
    provenance = env.get('provenance')
    if not isinstance(provenance, dict):
        fail('environment.provenance', 'must be an object')
        provenance = {}
    if not provenance:
        warnings.append('Engine/model/hardware provenance is missing; record it before interpreting comparisons.')
    for key, value in provenance.items():
        if not isinstance(key, str):
            fail('environment.provenance', 'field names must be strings')
        if value is not None and not isinstance(value, (str, int, float, bool)):
            fail('environment.provenance.' + str(key), 'must be a scalar value or null')
        if isinstance(value, float) and not math.isfinite(value):
            fail('environment.provenance.' + str(key), 'must be finite')
    def documented(value):
        return isinstance(value, str) and value.strip().lower() not in ('', 'unknown', 'unrecorded', 'todo', 'replace_me')
    for key in ('engine', 'engine_version', 'model_artifact', 'backend', 'hardware'):
        if not documented(provenance.get(key)):
            warnings.append('environment.provenance.' + key + ': missing or unspecified; document it for reproducibility')
    checksum = provenance.get('model_sha256')
    if not documented(checksum):
        warnings.append('Model artifact SHA-256 is unrecorded; a model name alone does not identify its exact weights.')
    elif re.fullmatch(r'[a-fA-F0-9]{64}', checksum) is None:
        fail('environment.provenance.model_sha256', 'must be a 64-character SHA-256 hex digest, or null/unknown')
    if not documented(provenance.get('cache_policy')):
        warnings.append('Cache reuse policy is not recorded; repeated prompts can confound comparisons.')
    if not documented(provenance.get('warmup_policy')):
        warnings.append('Warmup/cold-start policy is not recorded; keep cold and warmed measurements separate.')

    server = data.get('server')
    if not isinstance(server, dict):
        fail('server', 'must be an object')
        server = {}
    for field in ('base_url', 'model'):
        if not isinstance(server.get(field), str) or not server.get(field):
            fail('server.' + field, 'must be a nonempty string')
    if isinstance(server.get('base_url'), str):
        try:
            parsed_url = urlsplit(server['base_url'])
            if parsed_url.scheme not in ('http', 'https') or not parsed_url.hostname:
                raise ValueError()
            parsed_url.port
            if parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
                raise ValueError()
        except ValueError:
            fail('server.base_url', 'must be an HTTP(S) URL without credentials, query, or fragment')

    experiment = data.get('experiment')
    if not isinstance(experiment, dict):
        fail('experiment', 'must be an object')
        experiment = {}
    for field in ('name', 'prompt'):
        if not isinstance(experiment.get(field), str) or not experiment.get(field):
            fail('experiment.' + field, 'must be a nonempty string')
    prompt = experiment.get('prompt')
    if isinstance(prompt, str):
        try:
            digest = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
            if experiment.get('prompt_sha256') != digest:
                fail('experiment.prompt_sha256', 'does not match the UTF-8 prompt')
        except UnicodeError:
            fail('experiment.prompt', 'must be valid UTF-8 text')
    for field in ('request_count', 'concurrency', 'max_tokens'):
        value = experiment.get(field)
        if not _integer(value) or value < 1:
            fail('experiment.' + field, 'must be a positive integer')
    if _integer(experiment.get('concurrency')) and _integer(experiment.get('request_count')):
        if experiment['concurrency'] > experiment['request_count']:
            fail('experiment.concurrency', 'cannot exceed request_count')
    if not _number(experiment.get('temperature')) or experiment.get('temperature', -1) < 0:
        fail('experiment.temperature', 'must be a finite nonnegative number')
    seed = experiment.get('seed')
    if seed is not None and not _integer(seed):
        fail('experiment.seed', 'must be an integer or null')
    if not _number(experiment.get('timeout_seconds')) or experiment.get('timeout_seconds', 0) <= 0:
        fail('experiment.timeout_seconds', 'must be a finite positive number')
    run_duration_ok = nonnegative('duration_ms', data.get('duration_ms'))

    requests = data.get('requests')
    if not isinstance(requests, list):
        fail('requests', 'must be an array')
        requests = []
    if _integer(experiment.get('request_count')) and len(requests) != experiment['request_count']:
        fail('requests', 'count does not match experiment.request_count')
    identifiers, indexes = set(), set()
    missing_usage, failed, successful = 0, 0, 0
    for position, request in enumerate(requests):
        path = 'requests[%s]' % position
        if not isinstance(request, dict):
            fail(path, 'must be an object')
            continue
        key = request.get('request_id')
        identifier(path + '.request_id', key)
        if isinstance(key, str):
            if key in identifiers:
                fail(path + '.request_id', 'duplicate request ID')
            identifiers.add(key)
        index = request.get('index')
        if not _integer(index) or not 0 <= index < len(requests):
            fail(path + '.index', 'must be an integer in the request range')
        elif index in indexes:
            fail(path + '.index', 'duplicate request index')
        else:
            indexes.add(index)
        started_at = timestamp(path + '.started_at_utc', request.get('started_at_utc'))
        if created_at is not None and started_at is not None and run_duration_ok:
            offset = (started_at - created_at).total_seconds()
            if offset < -1 or offset > data['duration_ms'] / 1000 + 1:
                warnings.append(path + '.started_at_utc: outside the recorded run window; check clock changes or metadata')
        elapsed = request.get('elapsed_ms')
        elapsed_ok = nonnegative(path + '.elapsed_ms', elapsed)
        first = request.get('time_to_first_content_ms')
        first_ok = nonnegative(path + '.time_to_first_content_ms', first, nullable=True)
        if elapsed_ok and first_ok and first is not None and first > elapsed + 0.01:
            fail(path + '.time_to_first_content_ms', 'cannot exceed elapsed_ms')
        if elapsed_ok and run_duration_ok and elapsed > data['duration_ms'] + 1:
            fail(path + '.elapsed_ms', 'cannot exceed whole-run duration_ms')
        if type(request.get('fixture')) is not bool:
            fail(path + '.fixture', 'must be a boolean')
        if mode == 'live' and request.get('fixture') is True:
            fail(path + '.fixture', 'fixture response cannot appear in a live artifact')
        if type(request.get('done_received')) is not bool:
            fail(path + '.done_received', 'must be a boolean')
        http_status = request.get('http_status')
        if http_status is not None and (not _integer(http_status) or not 100 <= http_status <= 599):
            fail(path + '.http_status', 'must be a valid HTTP status integer or null')
        finish = request.get('finish_reason')
        if finish is not None and (not isinstance(finish, str) or not finish):
            fail(path + '.finish_reason', 'must be a nonempty string or null')
        status = request.get('status')
        if status == 'ok':
            successful += 1
            if not request.get('done_received') or not isinstance(finish, str) or not finish:
                fail(path, 'successful request requires finish_reason and the stream completion marker')
            if request.get('error') is not None:
                fail(path + '.error', 'must be null for a successful request')
            if not _integer(http_status) or not 200 <= http_status <= 299:
                fail(path + '.http_status', 'successful request requires a 2xx HTTP status')
        elif status == 'error':
            failed += 1
            error = request.get('error')
            if not isinstance(error, dict) or not all(isinstance(error.get(k), str) and error[k] for k in ('type', 'message')):
                fail(path + '.error', 'failed request requires nonempty type and message')
        else:
            fail(path + '.status', 'must be ok or error')
        if require_success and status != 'ok':
            fail(path + '.status', '--require-success requires a successful request')
        chunks = request.get('content_chunks')
        if not isinstance(chunks, list):
            fail(path + '.content_chunks', 'must be an array')
            chunks = []
        if not _integer(request.get('content_chunk_count')) or request.get('content_chunk_count') != len(chunks):
            fail(path + '.content_chunk_count', 'must equal the number of content chunks')
        previous, first_content, text_parts = -1, None, []
        for chunk_index, chunk in enumerate(chunks):
            chunk_path = path + '.content_chunks[%s]' % chunk_index
            if not isinstance(chunk, dict):
                fail(chunk_path, 'must be an object')
                continue
            at = chunk.get('at_ms')
            valid_at = nonnegative(chunk_path + '.at_ms', at)
            if valid_at:
                if at < previous:
                    fail(chunk_path + '.at_ms', 'chunk arrival times must be nondecreasing')
                if elapsed_ok and at > elapsed + 0.01:
                    fail(chunk_path + '.at_ms', 'cannot exceed elapsed_ms')
                previous = at
            text = chunk.get('text')
            if not isinstance(text, str):
                fail(chunk_path + '.text', 'must be a string')
            else:
                text_parts.append(text)
                if text and first_content is None and valid_at:
                    first_content = at
        if not isinstance(request.get('output_text'), str) or request.get('output_text') != ''.join(text_parts):
            fail(path + '.output_text', 'must equal concatenated recorded content chunks')
        if first_content is None:
            if first is not None:
                fail(path + '.time_to_first_content_ms', 'must be null when no visible content arrived')
            if status == 'ok':
                warnings.append(path + ': completed without visible content; review the prompt and finish reason')
            if require_success:
                fail(path + '.output_text', '--require-success requires visible content')
        elif not first_ok or first is None or abs(first - first_content) > 0.01:
            fail(path + '.time_to_first_content_ms', 'must match the first nonempty content chunk')
        usage = request.get('usage')
        if usage is None:
            missing_usage += 1
        elif not isinstance(usage, dict):
            fail(path + '.usage', 'must be an object or null')
        else:
            for field in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                value = usage.get(field)
                if field not in usage or (value is not None and (not _integer(value) or value < 0)):
                    fail(path + '.usage.' + field, 'must be a nonnegative integer or null')
            values = [usage.get(field) for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
            if all(_integer(value) and value >= 0 for value in values) and values[0] + values[1] != values[2]:
                fail(path + '.usage.total_tokens', 'must equal prompt_tokens + completion_tokens')
            if usage.get('completion_tokens') is None:
                missing_usage += 1
    if failed:
        warnings.append('%s request(s) failed; a structurally valid error record is not a successful experiment.' % failed)
    if missing_usage:
        warnings.append('%s request(s) lack server-reported completion-token usage; aggregate token throughput is unavailable.' % missing_usage)
    if successful < 20:
        warnings.append('Fewer than 20 successful samples: reported p95 is descriptive, not a stable tail-latency estimate.')
    if expected is not None:
        if not isinstance(expected, dict):
            fail('expected', 'must be an object')
        else:
            for key, value in expected.items():
                if key == 'model':
                    actual = server.get('model')
                elif key == 'mode':
                    actual = mode
                elif key in experiment:
                    actual = experiment[key]
                else:
                    fail('expected.' + str(key), 'unknown configuration field')
                    continue
                if actual != value:
                    fail('expected.' + str(key), 'recorded configuration does not match expectation')
    return {'valid': not errors, 'errors': errors, 'warnings': warnings}
