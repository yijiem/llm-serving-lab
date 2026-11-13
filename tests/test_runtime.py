import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from serving_lab.__main__ import main
from serving_lab.runtime import doctor, load_environment, run_experiment, save_json
from test_client import FixtureServer


class ExperimentTests(unittest.TestCase):
    def test_concurrent_capture_has_provenance_and_wall_time(self):
        with FixtureServer(pause=0.03) as server:
            result = run_experiment(server.url, 'fixture-model', 'test', request_count=4,
                                    concurrency=2, name='concurrency-study')
            self.assertEqual(2, server.max_active)
        self.assertEqual('fixture', result['mode'])
        self.assertEqual([0, 1, 2, 3], [r['index'] for r in result['requests']])
        self.assertEqual(4, len({r['request_id'] for r in result['requests']}))
        self.assertEqual(hashlib.sha256(b'test').hexdigest(), result['experiment']['prompt_sha256'])
        self.assertTrue(all(r['status'] == 'ok' for r in result['requests']))
        self.assertGreaterEqual(result['duration_ms'], max(r['elapsed_ms'] for r in result['requests']))
        for private_key in ('hostname', 'username', 'home', 'api_key'):
            self.assertNotIn(private_key, result['environment'])

    def test_validation_of_parameters_happens_before_network(self):
        for kwargs in ({'request_count': 0}, {'concurrency': 2}, {'max_tokens': 0},
                       {'temperature': float('nan')}, {'timeout': 0}, {'prompt': ''}):
            params = {'base_url': 'http://127.0.0.1:9', 'model': 'test', 'prompt': 'test'}
            params.update(kwargs)
            with self.assertRaises(ValueError):
                run_experiment(**params)

    def test_environment_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'env.json'
            path.write_text(json.dumps({'engine': 'llama.cpp', 'parallel_slots': 4}))
            self.assertEqual(4, load_environment(path)['provenance']['parallel_slots'])
            path.write_text(json.dumps({'api_key': 'never-copy'}))
            with self.assertRaises(ValueError):
                load_environment(path)
        self.assertIn('python_version', doctor())

    def test_exclusive_writes_keep_original_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'artifact.json'
            save_json(path, {'original': True})
            with self.assertRaises(FileExistsError):
                save_json(path, {'original': False})
            self.assertEqual({'original': True}, json.loads(path.read_text()))

    def test_cli_capture_and_sweep(self):
        with tempfile.TemporaryDirectory() as temp, FixtureServer() as server:
            folder = Path(temp)
            prompt = folder / 'prompt.txt'
            prompt.write_text('A synthetic public prompt.')
            common = ['--base-url', server.url, '--model', 'fixture-model', '--prompt-file', str(prompt)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                output = folder / 'capture.json'
                self.assertEqual(0, main(['capture'] + common + ['--output', str(output)]))
                self.assertEqual(1, main(['capture'] + common + ['--output', str(output)]))
                sweep = folder / 'sweep'
                self.assertEqual(0, main(['sweep'] + common + ['--requests', '4', '--output', str(sweep)]))
            self.assertEqual('fixture', json.loads(output.read_text())['mode'])
            self.assertEqual(['concurrency-1.json', 'concurrency-2.json', 'concurrency-4.json'],
                             sorted(p.name for p in sweep.iterdir()))

    def test_cli_failed_requests_are_saved_and_nonzero(self):
        with tempfile.TemporaryDirectory() as temp, FixtureServer(status=503) as server:
            prompt = Path(temp) / 'prompt.txt'
            prompt.write_text('test')
            output = Path(temp) / 'failure.json'
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(['capture', '--base-url', server.url, '--model', 'fixture-model',
                             '--prompt-file', str(prompt), '--output', str(output)])
            self.assertEqual(2, code)
            artifact = json.loads(output.read_text())
            self.assertEqual('error', artifact['requests'][0]['status'])
            self.assertEqual('fixture', artifact['mode'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(['validate', str(output)]))
                self.assertEqual(1, main(['validate', str(output), '--require-success']))

    def test_captured_fixture_validates_but_cannot_count_as_live(self):
        with tempfile.TemporaryDirectory() as temp, FixtureServer() as server:
            artifact = run_experiment(server.url, 'fixture-model', 'A synthetic public prompt.')
            path = Path(temp) / 'fixture.json'
            report = Path(temp) / 'summary.md'
            save_json(path, artifact)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(0, main(['validate', str(path)]))
                self.assertEqual(0, main(['validate', str(path), '--require-success']))
                self.assertEqual(1, main(['validate', str(path), '--require-live']))
                self.assertEqual(0, main(['summarize', str(path), '--output', str(report)]))
                self.assertEqual(1, main(['summarize', str(path), '--output', str(report)]))
            self.assertIn('fixture', report.read_text().lower())


if __name__ == '__main__':
    unittest.main()
