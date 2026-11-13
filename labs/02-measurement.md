# Lab 2 — Measure one streamed request correctly

**Estimated effort:** 90–150 minutes. Suggested checkpoints: define measurements, collect a baseline, inspect the collector, and write the interpretation.

## Goal and skills

Understand what the client can observe and use an existing collector without confusing network events with model events. You will practice monotonic timing, stream-completion handling, provenance, and validation of recorded measurements.

## Preparation

- Complete [Lab 1](01-local-serving.md).
- Read the official [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/b12110/tools/server/README.md), especially streaming and the metrics endpoint.
- Read the definitions below before investigating attention or KV-cache internals.

## Measurement definitions

| Quantity | Meaning in this lab | Limitation |
|---|---|---|
| Time to first content | Time from the collector starting a request until its first nonempty visible content arrives | Includes client/transport/server effects. It is not a direct measurement of prefill or a guaranteed engine TTFT. |
| Request duration | Client-measured elapsed time until the stream completes or fails | Includes waiting and communication as well as inference. |
| Content chunks | Nonempty visible-content events observed by the collector | A chunk can contain several tokens; chunk count is not token count. |
| Completion tokens | Token usage reported by the server, when supplied | Unknown if omitted. Do not substitute words, characters, or chunks. |
| Run wall time | Elapsed time for all work in one collected condition | Used for aggregate throughput; distinguish it from individual request durations. |

The collector uses a monotonic clock for durations and UTC timestamps for chronology. Do not subtract wall-clock timestamps to reconstruct precise latency when monotonic measurements are available.

## Procedure

### 1. State your observable contract

Write the following in `work/lab02/report.md`, with your own explanation:

- What counts as the first visible text? Empty metadata or reasoning-only events must not silently become visible answer text.
- What counts as completion? How would an abruptly closed stream differ from a completed response?
- Which quantities require the server's usage or metrics?

### 2. Keep the first request separate

Retain Lab 1's first-after-startup artifact. Make one additional short request if needed to confirm readiness. Describe what “warm” means operationally: for example, model loaded and one request already completed. This does not prove all caches are warm or all compilation is finished.

### 3. Collect a repeated baseline

```sh
python3 -m serving_lab capture \
  --model lab-model --prompt-file prompts/short.txt \
  --environment configs/environment.json \
  --max-tokens 64 --temperature 0 --seed 42 \
  --requests 8 --concurrency 1 \
  --name lab02-warm-repeated-prompt \
  --output runs/lab02-baseline.json

python3 -m serving_lab validate runs/lab02-baseline.json --require-live --require-success
python3 -m serving_lab summarize runs/lab02-baseline.json \
  --output runs/lab02-summary.md
```

The exact same prompt may reuse a prefix cache. Record the actual cache policy; do not describe these eight requests as eight independent cold-prefill trials. The generated summary must remain distinguishable from your own interpretation in `work/lab02/report.md`.

### 4. Inspect the implementation

Trace the capture command through `serving_lab/`. Find where it:

1. Creates the request and starts the timer.
2. Parses streamed events, including Unicode and event boundaries.
3. Recognizes the first visible content.
4. Handles finish reasons, usage, errors, and stream termination.
5. Writes an artifact without replacing earlier evidence.

Run the offline tests again. Ask Codex to explain one stream-parsing test and one failure-path test in plain language. The goal is to understand the instrument, not to assume tests prove every deployment will behave correctly.

### 5. Check a few calculations independently

Choose two completed requests and compare their recorded values. Confirm that first-content time is nonnegative and no greater than request duration. Compare the summary's sample count with the artifact.

If token usage is available for every required request, aggregate token throughput is based on total reported completion tokens divided by the complete run's wall time. Averaging per-request tokens/second is not an equivalent aggregate throughput calculation under concurrency.

The empirical p95 uses the documented nearest-rank calculation. With eight samples it is essentially a tail observation from a tiny sample, not a robust production percentile or service-level guarantee.

## Expected outcomes and interpretation

- Repeated requests usually vary in timing even with identical prompts and settings.
- The output may finish before its token ceiling.
- Missing usage leaves token-derived measurements unavailable; this is an honest result.
- Client timings can reveal an initial wait and continuing output, but cannot by themselves assign the delay to queueing, tokenization, prefill, or networking.

Explain at least two limitations of the measurements. Do not fabricate precision by labeling chunk intervals as inter-token latency.

## Deliverables and completion criteria

- Baseline artifact and generated summary.
- `work/lab02/report.md` with measurement definitions, independent checks, and limitations.
- A short explanation of one parser test and one failure test.

The lab is complete when you have successful real-model baseline requests, the artifacts validate, and your report accurately distinguishes measured quantities from inferred internal behavior. A valid artifact containing only correctly recorded failures does not demonstrate a successful baseline.

## Optional programming exercise

Write `work/stream_client.py` in Python or an equivalent Go client that records first-content and completion times. Use the provided collector as a reference, not as evidence that your own parser is correct. Add deterministic tests using synthetic streamed events, including empty metadata, split Unicode, and premature closure. Compare both clients on the same server without requiring identical timing or model text. This extension is not necessary to begin Lab 3.

Continue with [Lab 3](03-controlled-experiments.md).
