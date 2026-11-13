"""Streaming HTTP client. Network content chunks are never counted as tokens."""
import json
import http.client
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024


class ProtocolError(ValueError):
    """The server did not return a complete, valid streaming response."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, response_headers, newurl):
        # In particular, do not forward LAB_API_KEY to a different host.
        return None


def _open(request, timeout):
    return urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def normalize_base_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Base URL must be an http:// or https:// server URL.')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Do not put credentials, queries, or fragments in the base URL.')
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError('Base URL contains an invalid port.') from exc
    base = value.rstrip('/')
    return base[:-3] if base.endswith('/v1') else base


def headers(api_key=None):
    result = {'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
    if api_key:
        result['Authorization'] = 'Bearer ' + api_key
    return result


def _response_chunks(response, deadline, maximum_bytes):
    """Read available bytes instead of waiting for a complete SSE line.

    HTTPResponse.read1 performs at most one underlying buffered read. Updating
    the socket timeout also bounds an idle read by the time remaining, rather
    than restarting the entire request timeout for each read.
    """
    total = 0
    while True:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError('Request exceeded its time limit.')
        # urllib exposes an HTTPResponse whose buffered reader owns this socket.
        # BytesIO protocol fixtures have no socket and still use read1 below.
        sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
        if sock is not None:
            sock.settimeout(remaining)
        chunk = response.read1(8192)
        if time.perf_counter() > deadline:
            raise TimeoutError('Request exceeded its time limit.')
        if not chunk:
            return
        total += len(chunk)
        if total > maximum_bytes:
            raise ProtocolError('Server response exceeded the byte limit.')
        yield chunk


def sse_events(response, deadline, maximum_bytes=MAX_RESPONSE_BYTES):
    """Decode SSE data events, preserving UTF-8 across network reads.

    SSE events may contain several data lines. Comments and non-data fields
    do not form model output. Bounds apply even when a peer never sends a blank
    line. UTF-8 is decoded only after a complete line has been assembled.
    """
    data = []
    event_bytes = 0
    pending = b''
    first_line = True

    def lines():
        nonlocal pending
        for chunk in _response_chunks(response, deadline, maximum_bytes):
            pending += chunk
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                yield line + b'\n'
            if event_bytes + len(pending) > MAX_EVENT_BYTES:
                raise ProtocolError('Streaming event exceeded the byte limit.')
        if pending:
            yield pending

    for line in lines():
        event_bytes += len(line)
        if event_bytes > MAX_EVENT_BYTES:
            raise ProtocolError('Streaming event exceeded the byte limit.')
        try:
            text = line.decode('utf-8').rstrip('\r\n')
        except UnicodeDecodeError as exc:
            raise ProtocolError('Server sent invalid UTF-8.') from exc
        if first_line:
            text = text.lstrip('\ufeff')  # SSE permits a leading UTF-8 BOM.
            first_line = False
        if not text:
            if data:
                yield '\n'.join(data)
            data = []
            event_bytes = 0
        elif text.startswith('data:'):
            payload = text[5:]
            data.append(payload[1:] if payload.startswith(' ') else payload)
    if data:
        yield '\n'.join(data)


def _safe_error(exc):
    # Do not copy arbitrary response bodies, URLs, or headers into public results.
    if isinstance(exc, urllib.error.HTTPError):
        return {'type': 'http_error', 'message': 'Server returned HTTP %s.' % exc.code}
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return {'type': 'timeout', 'message': 'Server did not complete within the timeout.'}
    if isinstance(exc, urllib.error.URLError):
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return {'type': 'timeout', 'message': 'Server did not complete within the timeout.'}
        return {'type': 'connection_error', 'message': 'Unable to connect to or read from the server.'}
    if isinstance(exc, ProtocolError):
        return {'type': 'protocol_error', 'message': str(exc)}
    return {'type': 'io_error', 'message': 'The server connection ended unexpectedly.'}


def stream_request(base_url, model, prompt, index=0, max_tokens=64,
                   temperature=0.0, seed=42, timeout=120.0, api_key=None,
                   fixture=False, maximum_bytes=MAX_RESPONSE_BYTES):
    """Return one request record, including partial evidence on failure."""
    base_url = normalize_base_url(base_url)
    record = {
        'request_id': str(uuid.uuid4()), 'index': index, 'status': 'error',
        'started_at_utc': utcnow(), 'elapsed_ms': 0.0,
        'time_to_first_content_ms': None, 'content_chunks': [],
        'content_chunk_count': 0, 'output_text': '', 'finish_reason': None,
        'done_received': False, 'usage': None, 'http_status': None,
        'error': None, 'fixture': bool(fixture),
    }
    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}],
               'max_tokens': max_tokens, 'temperature': temperature, 'seed': seed,
               'stream': True, 'stream_options': {'include_usage': True}}
    request = urllib.request.Request(base_url + '/v1/chat/completions',
                                     data=json.dumps(payload).encode('utf-8'),
                                     headers=headers(api_key), method='POST')
    start = time.perf_counter()
    try:
        with _open(request, timeout) as response:
            record['http_status'] = response.status
            record['fixture'] = record['fixture'] or response.headers.get(
                'X-Serving-Lab-Fixture', '').lower() == 'true'
            if 'text/event-stream' not in response.headers.get('Content-Type', '').lower():
                raise ProtocolError('Expected a text/event-stream response.')
            for event in sse_events(response, start + timeout, maximum_bytes):
                if event.strip() == '[DONE]':
                    record['done_received'] = True
                    break
                try:
                    item = json.loads(event)
                except (ValueError, TypeError) as exc:
                    raise ProtocolError('Malformed JSON in an SSE event.') from exc
                if not isinstance(item, dict):
                    raise ProtocolError('SSE event must be a JSON object.')
                if item.get('error') is not None:
                    raise ProtocolError('Server reported an error in the stream.')
                usage = item.get('usage')
                if usage is not None:
                    if not isinstance(usage, dict):
                        raise ProtocolError('Server usage must be an object.')
                    # Missing token accounting remains null, never estimated from text.
                    counts = {key: usage.get(key) for key in (
                        'prompt_tokens', 'completion_tokens', 'total_tokens')}
                    if any(value is not None and (type(value) is not int or value < 0)
                           for value in counts.values()):
                        raise ProtocolError('Server token counts must be nonnegative integers or null.')
                    if all(value is not None for value in counts.values()) and (
                            counts['prompt_tokens'] + counts['completion_tokens'] != counts['total_tokens']):
                        raise ProtocolError('Server total token count is inconsistent.')
                    record['usage'] = counts
                choices = item.get('choices', [])
                if not isinstance(choices, list):
                    raise ProtocolError('Server choices must be an array.')
                for choice in choices:
                    if not isinstance(choice, dict):
                        raise ProtocolError('Server choice must be an object.')
                    if choice.get('index', 0) != 0:
                        raise ProtocolError('Unexpected additional completion choice.')
                    delta = choice.get('delta')
                    if delta is None:
                        delta = {}
                    if not isinstance(delta, dict):
                        raise ProtocolError('Streaming delta must be an object.')
                    content = delta.get('content')
                    if content is not None and not isinstance(content, str):
                        raise ProtocolError('Text content must be a string.')
                    if content:
                        at_ms = round((time.perf_counter() - start) * 1000, 6)
                        if record['time_to_first_content_ms'] is None:
                            record['time_to_first_content_ms'] = at_ms
                        record['content_chunks'].append({'at_ms': at_ms, 'text': content})
                    reason = choice.get('finish_reason')
                    if reason is not None:
                        if not isinstance(reason, str) or not reason:
                            raise ProtocolError('Finish reason must be a nonempty string.')
                        record['finish_reason'] = reason
            if not record['done_received']:
                raise ProtocolError('Stream ended without the [DONE] marker.')
            if not record['finish_reason']:
                raise ProtocolError('Stream ended without a finish reason.')
            record['status'] = 'ok'
    except (OSError, ValueError, http.client.HTTPException) as exc:
        if isinstance(exc, urllib.error.HTTPError):
            record['http_status'] = exc.code
            record['fixture'] = record['fixture'] or exc.headers.get(
                'X-Serving-Lab-Fixture', '').lower() == 'true'
        record['error'] = _safe_error(exc)
    finally:
        record['elapsed_ms'] = round((time.perf_counter() - start) * 1000, 6)
        record['content_chunk_count'] = len(record['content_chunks'])
        record['output_text'] = ''.join(chunk['text'] for chunk in record['content_chunks'])
    return record


def get_json(base_url, path, timeout=10.0, api_key=None):
    request = urllib.request.Request(normalize_base_url(base_url) + path,
                                     headers=headers(api_key))
    deadline = time.perf_counter() + timeout
    with _open(request, timeout) as response:
        data = b''.join(_response_chunks(response, deadline, MAX_RESPONSE_BYTES))
        result = json.loads(data.decode('utf-8'))
        return result, response.headers.get('X-Serving-Lab-Fixture', '').lower() == 'true'


def check_server(base_url, timeout=10.0, api_key=None):
    """Discover the advertised model IDs; a health URL is optional across engines."""
    base_url = normalize_base_url(base_url)
    result = {'base_url': base_url, 'models': [], 'fixture': False, 'health': None}
    try:
        health, fixture = get_json(base_url, '/health', timeout, api_key)
        result['health'] = health
        result['fixture'] = fixture
    except (OSError, ValueError, http.client.HTTPException):
        result['health'] = 'Not available; checking the model-list endpoint.'
    models, fixture = get_json(base_url, '/v1/models', timeout, api_key)
    if not isinstance(models, dict) or not isinstance(models.get('data'), list):
        raise ProtocolError('Model-list endpoint returned an invalid object.')
    result['models'] = [item['id'] for item in models['data']
                        if isinstance(item, dict) and isinstance(item.get('id'), str)]
    if not result['models']:
        raise ProtocolError('The server did not advertise a model ID.')
    result['fixture'] = result['fixture'] or fixture
    return result
