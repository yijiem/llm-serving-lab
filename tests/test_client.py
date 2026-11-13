import io
import http.client
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from serving_lab.client import (ProtocolError, check_server, normalize_base_url,
                                sse_events, stream_request)


def event(item):
    return ('data: ' + json.dumps(item, ensure_ascii=False) + '\r\n\r\n').encode('utf-8')


def delta(content=None, reason=None, **extra):
    data = dict(extra)
    if content is not None:
        data['content'] = content
    return {'choices': [{'index': 0, 'delta': data, 'finish_reason': reason}]}


class FixtureServer:
    """A protocol fixture, not a model and never real performance evidence."""
    def __init__(self, body=None, status=200, content_type='text/event-stream',
                 fixture=True, pause=0.0, headers=None, write_pause=0.0):
        self.body = body if body is not None else (
            event(delta(role='assistant')) + event(delta(reasoning_content='hidden')) +
            event(delta('Hello ')) + event(delta('世界')) + event(delta(reason='stop')) +
            event({'choices': [], 'usage': {'prompt_tokens': 5, 'completion_tokens': 3,
                                           'total_tokens': 8}}) + b'data: [DONE]\r\n\r\n')
        self.status = status
        self.content_type = content_type
        self.fixture = fixture
        self.pause = pause
        self.headers = headers or {}
        self.write_pause = write_pause
        self.payloads = []
        self.auth = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __enter__(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                if owner.fixture:
                    self.send_header('X-Serving-Lab-Fixture', 'true')
                self.end_headers()
                data = {'data': [{'id': 'fixture-model'}]} if self.path == '/v1/models' else {'status': 'ok'}
                self.wfile.write(json.dumps(data).encode())

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                with owner.lock:
                    owner.payloads.append(payload)
                    owner.auth.append(self.headers.get('Authorization'))
                    owner.active += 1
                    owner.max_active = max(owner.max_active, owner.active)
                try:
                    self.send_response(owner.status)
                    self.send_header('Content-Type', owner.content_type)
                    if owner.fixture:
                        self.send_header('X-Serving-Lab-Fixture', 'true')
                    for name, value in owner.headers.items():
                        self.send_header(name, value)
                    self.end_headers()
                    time.sleep(owner.pause)
                    # Split UTF-8 and SSE fields across writes to mimic real transport.
                    for start in range(0, len(owner.body), 7):
                        self.wfile.write(owner.body[start:start + 7])
                        if owner.write_pause:
                            self.wfile.flush()
                            time.sleep(owner.write_pause)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    with owner.lock:
                        owner.active -= 1
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%s' % self.server.server_port
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class StreamingClientTests(unittest.TestCase):
    def test_real_http_stream_preserves_unicode_and_distinguishes_tokens(self):
        with FixtureServer() as server:
            result = stream_request(server.url, 'fixture-model', 'Public test prompt', api_key='test-secret')
            self.assertEqual('Bearer test-secret', server.auth[0])
        self.assertEqual('ok', result['status'])
        self.assertEqual('Hello 世界', result['output_text'])
        self.assertEqual(2, result['content_chunk_count'])
        self.assertEqual(3, result['usage']['completion_tokens'])
        self.assertTrue(result['fixture'])
        self.assertTrue(result['done_received'])
        self.assertEqual('stop', result['finish_reason'])
        self.assertEqual(result['content_chunks'][0]['at_ms'], result['time_to_first_content_ms'])
        self.assertLessEqual(result['time_to_first_content_ms'], result['elapsed_ms'])
        self.assertNotIn('test-secret', json.dumps(result))
        self.assertNotIn('hidden', result['output_text'])

    def test_sse_comments_multiline_json_and_crlf(self):
        raw = b': ping\r\nevent: message\r\nid: 123\r\ndata: {"a":\r\ndata: 1}\r\n\r\n'
        values = list(sse_events(io.BytesIO(raw), time.perf_counter() + 1))
        self.assertEqual({'a': 1}, json.loads(values[0]))
        bom = b'\xef\xbb\xbfdata: {"a": 1}\n\n'
        self.assertEqual({'a': 1}, json.loads(next(sse_events(
            io.BytesIO(bom), time.perf_counter() + 1))))

    def test_usage_absent_stays_unknown_and_empty_content_is_not_first_text(self):
        body = event(delta('')) + event(delta(reasoning_content='private reasoning')) + event(delta(reason='length')) + b'data: [DONE]\n\n'
        with FixtureServer(body) as server:
            result = stream_request(server.url, 'fixture-model', 'test')
        self.assertEqual('ok', result['status'])
        self.assertIsNone(result['usage'])
        self.assertIsNone(result['time_to_first_content_ms'])
        self.assertEqual(0, result['content_chunk_count'])

    def test_truncated_stream_retains_partial_output_but_is_error(self):
        with FixtureServer(event(delta('partial'))) as server:
            result = stream_request(server.url, 'fixture-model', 'test')
        self.assertEqual('error', result['status'])
        self.assertEqual('partial', result['output_text'])
        self.assertFalse(result['done_received'])
        self.assertEqual('protocol_error', result['error']['type'])

    def test_done_without_finish_reason_is_error(self):
        with FixtureServer(b'data: [DONE]\n\n') as server:
            result = stream_request(server.url, 'fixture-model', 'test')
        self.assertEqual('error', result['status'])
        self.assertIn('finish reason', result['error']['message'])

    def test_malformed_json_and_error_event_are_errors(self):
        for body in (b'data: {bad}\n\n', event({'error': {'message': 'do not publish'}})):
            with FixtureServer(body) as server:
                result = stream_request(server.url, 'fixture-model', 'test')
            self.assertEqual('error', result['status'])
            self.assertNotIn('do not publish', json.dumps(result))

    def test_http_error_body_is_not_saved(self):
        with FixtureServer(b'private upstream error text', status=500) as server:
            result = stream_request(server.url, 'fixture-model', 'test')
        self.assertEqual(500, result['http_status'])
        self.assertEqual('http_error', result['error']['type'])
        self.assertNotIn('private upstream error text', json.dumps(result))

    def test_redirect_is_not_followed_with_credentials(self):
        with FixtureServer(status=302, headers={'Location': 'http://127.0.0.1:9/elsewhere'}) as server:
            result = stream_request(server.url, 'fixture-model', 'test', api_key='test-secret')
        self.assertEqual(302, result['http_status'])
        self.assertEqual('http_error', result['error']['type'])

    def test_response_limits_and_deadline(self):
        with self.assertRaises(ProtocolError):
            list(sse_events(io.BytesIO(b'data: too much\n\n'), time.perf_counter() + 1, 5))
        with self.assertRaises(TimeoutError):
            list(sse_events(io.BytesIO(b''), time.perf_counter() - 1))
        with FixtureServer(pause=0.08) as server:
            result = stream_request(server.url, 'fixture-model', 'test', timeout=0.01)
        self.assertEqual('error', result['status'])
        self.assertEqual('timeout', result['error']['type'])

    def test_trickling_line_respects_deadline(self):
        # A socket inactivity timeout alone never fires while bytes keep arriving.
        with FixtureServer(b'data: ' + b'x' * 1000, write_pause=0.01) as server:
            result = stream_request(server.url, 'fixture-model', 'test', timeout=0.04)
        self.assertEqual('timeout', result['error']['type'])
        self.assertLess(result['elapsed_ms'], 500)

    def test_malformed_delta_and_usage_are_recorded_protocol_errors(self):
        cases = [event({'choices': [{'delta': value}]}) for value in ([], '', 0, False)]
        cases.extend(event({'usage': value}) for value in (
            {'completion_tokens': '3'}, {'completion_tokens': True},
            {'completion_tokens': -1},
            {'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 99}))
        for body in cases:
            with self.subTest(body=body), FixtureServer(event(delta('partial')) + body) as server:
                result = stream_request(server.url, 'fixture-model', 'test')
            self.assertEqual('error', result['status'])
            self.assertEqual('protocol_error', result['error']['type'])
            self.assertEqual('partial', result['output_text'])
            self.assertIsNone(result['usage'])

    def test_incomplete_health_response_falls_back_to_models(self):
        with patch('serving_lab.client.get_json', side_effect=[
                http.client.IncompleteRead(b'{'), ({'data': [{'id': 'fixture-model'}]}, True)]):
            result = check_server('http://127.0.0.1:8080')
        self.assertEqual(['fixture-model'], result['models'])
        self.assertTrue(result['fixture'])

    def test_invalid_utf8_and_nonstream_response(self):
        with self.assertRaises(ProtocolError):
            list(sse_events(io.BytesIO(b'data: \xff\n\n'), time.perf_counter() + 1))
        with FixtureServer(b'{}', content_type='application/json') as server:
            result = stream_request(server.url, 'fixture-model', 'test')
        self.assertEqual('protocol_error', result['error']['type'])

    def test_server_discovery_and_base_url_rules(self):
        with FixtureServer() as server:
            info = check_server(server.url + '/v1')
        self.assertEqual(['fixture-model'], info['models'])
        self.assertTrue(info['fixture'])
        for bad in ('file:///tmp/model', 'https://user:password@example.com',
                    'https://example.com?api_key=secret', 'https://example.com/#x',
                    'https://example.com:wrong'):
            with self.assertRaises(ValueError):
                normalize_base_url(bad)


if __name__ == '__main__':
    unittest.main()
