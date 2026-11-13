# Lab 4 — Concurrency, throughput, and waiting

**Estimated effort:** 90–150 minutes. Stop and reduce the workload if the machine becomes unresponsive; document any revised configuration.

## Goal and skills

Observe how several requests share a serving engine. You will distinguish client concurrency from engine batching, compare latency with aggregate throughput, and use server evidence to investigate waiting.

## Prerequisites

- Complete [Lab 3](03-controlled-experiments.md).
- Read the opening explanation of [continuous batching](https://huggingface.co/docs/transformers/main/continuous_batching). You do not need to use the Hugging Face API shown there.
- Locate the parallel-request and metrics options in [llama.cpp's server documentation](https://github.com/ggml-org/llama.cpp/blob/b12110/tools/server/README.md).

**Batching** groups work from multiple requests into a computation. **Continuous batching** changes the participating requests as work completes and new work is admitted. Each request keeps its own logical context. Exact scheduling, including the interleaving of prompt processing and generation, depends on the engine.

Opening four client connections does not prove four requests were executed in the same engine batch. Server capacity, slots, queueing, and scheduling determine what actually happens.

## Procedure

### 1. Record capacity and predictions

Verify the server's configured parallel slots and context capacity from Setup. Use the same configuration for every condition. Do not increase server slots between trials and attribute the difference solely to client concurrency.

Write predictions for concurrency 1, 2, and 4:

- Could aggregate throughput improve?
- Could an individual request wait longer?
- Where would the server queue work if it cannot process everything immediately?
- What observations would contradict your prediction?

Use the same prompt, token ceiling, and total request count for each condition. Record whether prefix reuse is allowed and whether an initial warmup has already occurred.

### 2. Run the sweep

```sh
python3 -m serving_lab sweep \
  --model lab-model --prompt-file prompts/generate.txt \
  --environment configs/environment.json \
  --max-tokens 64 --temperature 0 --seed 42 \
  --requests 8 --concurrency 1,2,4 \
  --name lab04-rep1 \
  --output runs/lab04-rep1
```

This produces one JSON artifact per concurrency condition, for example `concurrency-1.json`. A concurrency setting is a ceiling on the number of client requests in flight, not evidence that the engine used exactly that many slots throughout the run.

Repeat into fresh directories `runs/lab04-rep2` and `runs/lab04-rep3`. Reverse or rotate condition order in later repetitions if supported by the sweep argument, or collect conditions individually. Record the actual order.

### 3. Collect server evidence

If the server was started with metrics enabled, inspect `http://127.0.0.1:8080/metrics` before, during, and after a condition. Keep relevant snapshots or logs with timestamps and identify the associated run.

Look for active and deferred requests and prompt/generation measurements. A snapshot after all requests finish can miss the queue entirely. Sample while the workload runs, and note the sampling interval. Do not interpret a missing metric as zero.

Metrics names and meanings are engine-version dependent. Record the names actually exposed. Preserve the difference between server timing and client timing.

### 4. Validate and summarize

```sh
python3 -m serving_lab validate runs/lab04-rep*/*.json --require-live
python3 -m serving_lab summarize runs/lab04-rep*/*.json \
  --output runs/lab04-summary.md
```

Compare each condition using sample count, success/failure count, client first-content and completion times, complete run wall time, and aggregate token throughput only where reported usage is available.

The aggregate calculation is total reported output tokens divided by run wall time. It is not the average of each request's token rate. If some required token counts are absent, report token throughput as unavailable and retain the other measurements.

### 5. Explain one observation

Choose one difference between concurrency conditions. State the evidence and an alternative explanation. If you claim queueing or batching occurred, cite server logs or metrics that support that claim. A latency difference alone does not reveal the scheduler's internal decisions.

## Expected outcomes

- Increased concurrency may improve total throughput while increasing per-request latency.
- Improvement can flatten or reverse when memory, compute, context slots, or other resources become limiting.
- Small models and CPU/Metal execution can show different patterns from a large GPU deployment.
- Fixed sampling settings do not guarantee identical generated text or output length across concurrent runs.

These are possible behaviors, not required pass/fail trends. This lab does not establish a production capacity limit or a statistically reliable p99.

## Deliverables

- `work/lab04/report.md`, artifacts, and generated summary.
- A table or plot showing the conditions with sample counts and failures.
- At least one timestamped server observation, or an explicit description of the unavailable instrumentation.
- An explanation of client concurrency versus continuous batching.
- A discussion of small-sample uncertainty, caching, and actual output-length differences.

## Optional failure experiment

Use a separate labeled experiment to stop the server during a request or interrupt a client. Check that incomplete streams are retained as failures. Determine whether server work actually stops after client cancellation using logs or metrics; closing the client does not prove cancellation reached the engine. Do not mix these intentionally failed requests into the normal capacity comparison.

Continue with [Lab 5](05-capstone.md).
