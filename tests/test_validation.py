import copy
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from serving_lab.validation import validate_artifact


def example_artifact():
    prompt = 'Explain a queue.'
    return {
        'schema_version': 1, 'run_id': str(uuid4()), 'created_at_utc': '2026-01-01T12:00:00Z', 'mode': 'live',
        'environment': {'system': 'test-os', 'machine': 'test-cpu', 'python_version': '3.9', 'cpu_count': 2,
                        'provenance': {'engine_version': 'test-version', 'cache_policy': 'disabled',
                                       'warmup_policy': 'one unmeasured request'}},
        'server': {'base_url': 'http://127.0.0.1:8080', 'model': 'test-model'},
        'experiment': {'name': 'baseline', 'prompt': prompt,
                       'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                       'request_count': 1, 'concurrency': 1, 'max_tokens': 32,
                       'temperature': 0, 'seed': 42, 'timeout_seconds': 10},
        'duration_ms': 100,
        'requests': [{'request_id': str(uuid4()), 'index': 0, 'status': 'ok',
                      'started_at_utc': '2026-01-01T12:00:00Z', 'elapsed_ms': 90,
                      'time_to_first_content_ms': 20,
                      'content_chunks': [{'at_ms': 20, 'text': 'A '}, {'at_ms': 40, 'text': 'queue.'}],
                      'content_chunk_count': 2, 'output_text': 'A queue.', 'finish_reason': 'stop',
                      'done_received': True, 'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8},
                      'http_status': 200, 'error': None, 'fixture': False}],
    }


class ArtifactValidationTests(unittest.TestCase):
    def test_coherent_capture_and_expected_condition_are_valid(self):
        result = validate_artifact(example_artifact(), require_live=True,
                                   expected={'model': 'test-model', 'concurrency': 1, 'temperature': 0})
        self.assertTrue(result['valid'], result['errors'])
        self.assertTrue(any('Fewer than 20' in text for text in result['warnings']))
        self.assertTrue(any('not independent proof' in text for text in result['warnings']))

    def test_output_content_is_not_a_deterministic_answer_test(self):
        artifact = example_artifact()
        request = artifact['requests'][0]
        request['content_chunks'] = [{'at_ms': 20, 'text': '別の答え 🌿'}]
        request['content_chunk_count'] = 1
        request['output_text'] = '別の答え 🌿'
        self.assertTrue(validate_artifact(artifact)['valid'])

    def test_fixture_guard_and_mislabelled_live_capture_fail(self):
        artifact = example_artifact()
        artifact['mode'] = 'fixture'
        artifact['requests'][0]['fixture'] = True
        self.assertTrue(validate_artifact(artifact)['valid'])
        self.assertFalse(validate_artifact(artifact, require_live=True)['valid'])
        artifact['mode'] = 'live'
        self.assertFalse(validate_artifact(artifact)['valid'])

    def test_missing_usage_stays_unknown_and_is_a_warning(self):
        artifact = example_artifact()
        artifact['requests'][0]['usage'] = None
        result = validate_artifact(artifact)
        self.assertTrue(result['valid'])
        self.assertTrue(any('throughput is unavailable' in text for text in result['warnings']))

    def test_usage_arithmetic_negative_and_boolean_counts_are_rejected(self):
        for update in ({'total_tokens': 9}, {'completion_tokens': -1}, {'prompt_tokens': True}):
            artifact = example_artifact()
            artifact['requests'][0]['usage'].update(update)
            with self.subTest(update=update):
                self.assertFalse(validate_artifact(artifact)['valid'])

    def test_provenance_holes_are_warnings_not_fabricated_values(self):
        artifact = example_artifact()
        artifact['environment']['provenance'] = {}
        result = validate_artifact(artifact)
        self.assertTrue(result['valid'])
        self.assertTrue(any('provenance is missing' in text for text in result['warnings']))
        self.assertTrue(any('Cache reuse' in text for text in result['warnings']))
        self.assertTrue(any('Warmup/cold-start' in text for text in result['warnings']))

    def test_protocol_success_requires_completion_marker_and_finish_reason(self):
        for field, value in (('done_received', False), ('finish_reason', None), ('http_status', 500),
                             ('error', {'type': 'Error', 'message': 'failed'})):
            artifact = example_artifact()
            artifact['requests'][0][field] = value
            with self.subTest(field=field):
                self.assertFalse(validate_artifact(artifact)['valid'])

    def test_honest_failed_request_is_preserved_and_warned(self):
        artifact = example_artifact()
        request = artifact['requests'][0]
        request.update(status='error', done_received=False, finish_reason=None,
                       error={'type': 'ProtocolError', 'message': 'EOF before completion'})
        result = validate_artifact(artifact)
        self.assertTrue(result['valid'], result['errors'])
        self.assertTrue(any('not a successful experiment' in text for text in result['warnings']))

    def test_success_guard_rejects_failed_and_empty_requests_without_exact_text_matching(self):
        artifact = example_artifact()
        self.assertTrue(validate_artifact(artifact, require_success=True)['valid'])
        artifact['requests'][0].update(status='error', error={'type': 'timeout', 'message': 'Timed out'})
        self.assertTrue(validate_artifact(artifact)['valid'])
        self.assertFalse(validate_artifact(artifact, require_success=True)['valid'])
        artifact = example_artifact()
        artifact['requests'][0].update(content_chunks=[], content_chunk_count=0,
                                      output_text='', time_to_first_content_ms=None)
        self.assertTrue(validate_artifact(artifact)['valid'])
        self.assertFalse(validate_artifact(artifact, require_success=True)['valid'])

    def test_count_identity_prompt_and_expected_config_checks(self):
        artifact = example_artifact()
        artifact['experiment']['request_count'] = 2
        artifact['requests'].append(copy.deepcopy(artifact['requests'][0]))
        artifact['experiment']['prompt_sha256'] = 'incorrect'
        result = validate_artifact(artifact, expected={'concurrency': 4, 'nonexistent': 1})
        self.assertFalse(result['valid'])
        for phrase in ('duplicate request ID', 'duplicate request index', 'UTF-8 prompt',
                       'does not match expectation', 'unknown configuration field'):
            self.assertTrue(any(phrase in text for text in result['errors']), phrase)
        artifact['experiment']['request_count'] = 3
        self.assertTrue(any('count does not match' in text for text in validate_artifact(artifact)['errors']))

    def test_timing_and_recorded_text_consistency(self):
        variants = [
            {'elapsed_ms': float('nan')}, {'elapsed_ms': float('inf')}, {'elapsed_ms': -1},
            {'elapsed_ms': 1010}, {'time_to_first_content_ms': 99},
            {'content_chunk_count': 3}, {'output_text': 'invented replacement'},
            {'content_chunks': [{'at_ms': 20, 'text': 'A '}, {'at_ms': 10, 'text': 'queue.'}]},
            {'content_chunks': [{'at_ms': 20, 'text': 'A '}, {'at_ms': 120, 'text': 'queue.'}]},
        ]
        for update in variants:
            artifact = example_artifact()
            artifact['requests'][0].update(update)
            with self.subTest(update=update):
                self.assertFalse(validate_artifact(artifact)['valid'])

    def test_empty_content_has_no_first_content_time(self):
        artifact = example_artifact()
        artifact['requests'][0].update(content_chunks=[], content_chunk_count=0,
                                      output_text='', time_to_first_content_ms=None)
        result = validate_artifact(artifact)
        self.assertTrue(result['valid'])
        self.assertTrue(any('without visible content' in text for text in result['warnings']))
        artifact['requests'][0]['time_to_first_content_ms'] = 0
        self.assertFalse(validate_artifact(artifact)['valid'])

    def test_timestamps_and_malformed_containers_report_errors(self):
        for value in (None, [], 'text'):
            self.assertFalse(validate_artifact(value)['valid'])
        for field, value in (('created_at_utc', 'not-a-date'), ('created_at_utc', '2026-01-01T12:00:00'),
                             ('environment', None), ('server', []), ('experiment', None), ('requests', 'not-array')):
            artifact = example_artifact()
            artifact[field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(validate_artifact(artifact)['valid'])

    def test_clock_inconsistency_is_reported_without_discarding_monotonic_timings(self):
        artifact = example_artifact()
        artifact['requests'][0]['started_at_utc'] = '2026-01-01T13:00:00Z'
        result = validate_artifact(artifact)
        self.assertTrue(result['valid'])
        self.assertTrue(any('outside the recorded run window' in warning for warning in result['warnings']))

    def test_malformed_unicode_numbers_and_urls_report_errors_without_raising(self):
        artifact = example_artifact()
        artifact['experiment']['prompt'] = '\ud800'
        self.assertFalse(validate_artifact(artifact)['valid'])
        artifact = example_artifact()
        artifact['duration_ms'] = 10 ** 400
        self.assertFalse(validate_artifact(artifact)['valid'])
        for url in ('file:///private/file', 'http://user:secret@localhost:8080',
                    'http://localhost:8080?token=secret', 'http://localhost:8080#secret',
                    'http://localhost:999999', 'http://['):
            artifact = example_artifact()
            artifact['server']['base_url'] = url
            with self.subTest(url=url):
                self.assertFalse(validate_artifact(artifact)['valid'])

    def test_model_digest_is_verified_as_a_digest_not_a_name(self):
        artifact = example_artifact()
        artifact['environment']['provenance']['model_sha256'] = 'my-model.gguf'
        self.assertFalse(validate_artifact(artifact)['valid'])
        artifact['environment']['provenance']['model_sha256'] = 'a' * 64
        self.assertTrue(validate_artifact(artifact)['valid'])

    def test_runtime_artifact_roundtrips_cli_validation_and_summary(self):
        from serving_lab.__main__ import main
        from serving_lab.runtime import run_experiment, save_json
        from test_client import FixtureServer

        with FixtureServer() as server:
            artifact = run_experiment(server.url, 'fixture-model', 'Public synthetic prompt',
                                      request_count=2, concurrency=2)
        self.assertTrue(validate_artifact(artifact)['valid'])
        self.assertEqual('fixture', artifact['mode'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.json'
            report = Path(directory) / 'report.md'
            save_json(path, artifact)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, main(['validate', str(path)]))
            parsed = json.loads(output.getvalue())
            self.assertTrue(parsed['valid'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(1, main(['validate', str(path), '--require-live']))
                self.assertEqual(0, main(['summarize', str(path), '--output', str(report)]))
            text = report.read_text()
            self.assertIn(artifact['run_id'], text)
            self.assertIn('fixture', text)
            self.assertIn('2 / 0', text)


if __name__ == '__main__':
    unittest.main()
