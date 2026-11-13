import copy
import csv
import io
import unittest
from uuid import uuid4

from serving_lab.summary import comparison_notes, percentile, summary_csv, summary_rows, summarize_artifacts
from test_validation import example_artifact


class ArtifactSummaryTests(unittest.TestCase):
    def test_aggregate_throughput_uses_wall_time_not_mean_request_rates(self):
        artifact = example_artifact()
        second = copy.deepcopy(artifact['requests'][0])
        second.update(request_id=str(uuid4()), index=1, elapsed_ms=50)
        second['usage'] = {'prompt_tokens': 5, 'completion_tokens': 7, 'total_tokens': 12}
        artifact['requests'].append(second)
        artifact['experiment'].update(request_count=2, concurrency=2)
        row = summary_rows([artifact])[0]
        # (3 + 7) generated tokens / 0.100s whole-run wall time = 100 tokens/s.
        self.assertEqual(100, row['output_tokens_per_second'])
        self.assertEqual(10, row['completion_tokens_total'])
        self.assertEqual(70, row['elapsed_p50_ms'])
        self.assertEqual(90, row['elapsed_p95_ms'])

    def test_one_missing_usage_value_prevents_aggregate_token_claim(self):
        artifact = example_artifact()
        artifact['requests'][0]['usage'] = None
        row = summary_rows([artifact])[0]
        self.assertIsNone(row['completion_tokens_total'])
        self.assertIsNone(row['output_tokens_per_second'])
        self.assertIn('unavailable', summarize_artifacts([artifact]))
        csv_row = next(csv.DictReader(io.StringIO(summary_csv([artifact]))))
        self.assertEqual('', csv_row['output_tokens_per_second'])

    def test_zero_walltime_does_not_divide_by_zero(self):
        artifact = example_artifact()
        artifact['duration_ms'] = 0
        request = artifact['requests'][0]
        request['elapsed_ms'] = request['time_to_first_content_ms'] = 0
        for chunk in request['content_chunks']:
            chunk['at_ms'] = 0
        self.assertIsNone(summary_rows([artifact])[0]['output_tokens_per_second'])

    def test_errors_do_not_silently_enter_success_latency_distribution(self):
        artifact = example_artifact()
        request = artifact['requests'][0]
        request.update(status='error', done_received=False, finish_reason=None,
                       error={'type': 'ReadError', 'message': 'connection lost'})
        row = summary_rows([artifact])[0]
        self.assertEqual(1, row['errors'])
        self.assertEqual(0, row['successful'])
        self.assertIsNone(row['elapsed_p95_ms'])
        self.assertIn('failed', summarize_artifacts([artifact]))

    def test_nearest_rank_tail_and_small_sample_caveat(self):
        self.assertEqual(19, percentile(list(range(1, 21)), 95))
        self.assertEqual(9, percentile([2, 9], 95))
        self.assertIsNone(percentile([], 95))
        report = summarize_artifacts([example_artifact()])
        self.assertIn('not confidence bounds', report)
        self.assertIn('not an exact model-token timestamp', report)

    def test_compared_modes_warmups_and_models_remain_separate(self):
        first = example_artifact()
        second = copy.deepcopy(first)
        second['run_id'] = str(uuid4())
        second['mode'] = 'fixture'
        second['requests'][0]['fixture'] = True
        second['server']['model'] = 'different-model'
        second['environment']['provenance']['warmup_policy'] = 'cold'
        self.assertEqual(2, len(summary_rows([first, second])))
        notes = ' '.join(comparison_notes([first, second]))
        self.assertIn('mode (live versus fixture)', notes)
        self.assertIn('model identifier', notes)
        self.assertIn('warmup/cache policies', notes)
        self.assertIn('never pooled', notes)

    def test_bad_artifact_is_not_silently_summarized(self):
        artifact = example_artifact()
        artifact['requests'][0]['output_text'] = 'edited'
        with self.assertRaises(ValueError):
            summarize_artifacts([artifact])

    def test_markdown_escapes_names_and_csv_roundtrips(self):
        artifact = example_artifact()
        artifact['experiment']['name'] = 'test|name\nnew line'
        self.assertIn('test\\|name new line', summarize_artifacts([artifact]))
        row = next(csv.DictReader(io.StringIO(summary_csv([artifact]))))
        self.assertEqual(artifact['experiment']['name'], row['experiment'])
        self.assertEqual(artifact['run_id'], row['run_id'])


if __name__ == '__main__':
    unittest.main()
