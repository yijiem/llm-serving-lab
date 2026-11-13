# Verification and experimental validity

There are three different questions: does the tooling work, is the evidence internally consistent, and does the evidence support the conclusion? Use a different check for each.

## 1. Offline software tests

```sh
python3 -m unittest discover -s tests -q
```

Tests use deterministic synthetic data and local mock HTTP/SSE responses. They cover framing, split Unicode, metadata versus text, missing usage, explicit errors, truncation, timeouts, concurrent request accounting, no-overwrite behavior, validation, and summary math. Asset tests use tiny local archives. No model weights, hosted API, or accelerator is involved. CI runs the same suite.

Wall-clock tests check broad invariants, not exact elapsed milliseconds. Passing these tests establishes something about the toolkit; it is not a model benchmark or completed student experiment.

## 2. Artifact checks

```sh
python3 -m serving_lab validate runs/first.json --require-live --require-success
```

- Default validation checks structure, counts, IDs, hashes, finite/nonnegative timings, content assembly, usage arithmetic, and completion evidence. A faithfully recorded failed request can be **valid evidence**.
- `--require-live` rejects artifacts labeled as fixtures. This avoids accidental fixture submission. It is not cryptographic attestation that a model ran.
- `--require-success` additionally requires every request to have completed successfully with visible text. Use it for the first working-server milestone; omit it when intentionally examining failures.
- Missing provenance or a small sample can produce warnings. Missing usage is allowed and stays unknown. A valid file may still be insufficient for a strong conclusion.

Capture/sweep exits `0` when requests succeed, `2` when an artifact was saved with request failures, and `1` for setup/argument/file errors. Validate exits `0` if the requested checks pass and `1` if they fail. Do not discard captures solely because their command exited nonzero.

## 3. Measurement semantics

| Field or summary | Meaning and limitation |
| --- | --- |
| `time_to_first_content_ms` | Client elapsed time from starting the HTTP operation until the first parsed nonempty visible content delta. Includes connection, queueing, computation, transport, and buffering. It is not an engine-internal TTFT measurement. |
| Request `elapsed_ms` | Client elapsed time for the request, including response parsing and stream completion or failure handling. |
| Run `duration_ms` | Whole experiment wall time, including dispatch and waiting for all submitted work. |
| `content_chunks` | Parsed content deltas and relative receive times. One chunk may contain several tokens or buffered text; chunk counts and gaps are not token counts and token latency. |
| `usage` | Counts supplied by the server. Unavailable counts remain null. Reasoning-token accounting can differ by backend. |
| Aggregate output throughput | Sum of reported completion tokens across all requests divided by whole-run seconds. Includes prefill/queueing effects; not pure decode speed. If any request lacks completion-token usage, throughput is unknown. Inspect the error count alongside this metric. |
| p50 / p95 | p50 is the sample median; p95 uses empirical nearest rank, computed separately per condition from successful requests. With fewer than 20 samples, p95 is the maximum and is descriptive, not a reliable tail estimate. |

Read the current JSON fields and source when extending the collector. The tool sends an OpenAI-compatible chat-completions streaming request (`n=1`) with usage requested. Compatibility is a practical subset, not certification against every backend. Unexpected protocol data should remain a visible error rather than silently become a successful measurement.

The current runner uses a bounded client thread pool. At most the selected number of requests is active; a new one begins when a worker is free. Request clocks begin when a worker starts sending, so waiting in the client's executor queue is reflected in **whole-run duration**, not individual request duration. This is a finite batch experiment, not an open-loop arrival-rate load generator. It does not reveal the server scheduler by itself.

## 4. Human review

Use the report template to state a hypothesis **before** measuring. Review:

1. Were model, precision, engine, hardware, context, slots, and sampling settings held constant?
2. Were warmups, trial order, prefix reuse, thermal effects, and unrelated load handled or acknowledged?
3. Were actual output lengths and failures reported, not hidden behind a configured token cap?
4. Are the plots and calculations traceable to the exact raw files and code revision?
5. Does the conclusion stay within the experiment? Higher concurrency alone does not prove continuous batching or a particular KV-cache mechanism.

Expected trends are hypotheses. A result contrary to expectation can earn full credit when investigated and reported clearly. No universal tokens/second target is used.

## Reproducible does not mean identical

Pinned software, model hashes, synthetic prompts, explicit settings, and preserved raw captures allow another person to audit and repeat your method. Even with temperature 0 and a fixed seed, floating-point kernels, backend versions, batching, scheduling, and hardware can change generated text and timings. Test protocol invariants and evidence quality rather than exact prose.

The toolkit records prompts and outputs. Before moving selected files from ignored `runs/` into tracked `submissions/`, review their full contents and use only appropriate public material. API keys are read from `LAB_API_KEY` if supplied; the collector does not put that header into artifacts. Do not put secrets in prompts, URLs, or notes.
