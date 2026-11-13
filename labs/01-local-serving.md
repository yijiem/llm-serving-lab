# Lab 1 — Run one local model

**Estimated effort:** 60–120 minutes, including setup. Download or build time varies by machine.

## Goal and outcomes

Run an existing pretrained model as a local service and capture one complete response. You will learn model provenance, server readiness, request configuration, and the difference between a transport success and a verified model-serving experiment.

## Before you start

- Complete the component-boundary exercise in [Lab 0](00-foundations.md).
- Read [Setup](../docs/setup.md), including the hardware choices and pinned assets.
- Skim the official [llama.cpp server usage](https://github.com/ggml-org/llama.cpp/blob/b12110/tools/server/README.md). Look for model loading, the listening address, health, models, and chat completion endpoints. You do not need to understand all command-line flags.

Use **llama.cpp only** for the core labs. vLLM is an optional later comparison. No model training or cache implementation is required.

## Procedure

### 1. Check the local tools

From the repository root:

```sh
python3 -m serving_lab doctor
python3 -m unittest discover -s tests -v
```

The tests use controlled fixtures. They verify the measurement and validation software without downloading a model or starting a GPU workload. A passing test run is **not evidence that you have served a real model**.

Record your Python version and platform. Resolve a failing offline test before interpreting model measurements.

### 2. Obtain and start the pinned model

Follow [Setup](../docs/setup.md) exactly for asset download, hash verification, environment metadata, and the server command. Keep the server terminal available so you can inspect loading failures and logs.

Why: a model identifier alone does not identify its exact weights, quantization, engine build, backend, or context configuration. These can materially affect performance.

The setup uses the server alias `lab-model`. In your client terminal:

```sh
export LAB_MODEL='lab-model'
python3 -m serving_lab check-server --base-url http://127.0.0.1:8080
```

Confirm that the server is ready and its advertised model matches the alias. “Port open” is not sufficient if the model is still loading. Do not run a second server against the same port just because loading is slow.

### 3. Describe the experiment before running it

Copy [the report template](../templates/report.md) to `work/lab01/report.md`. Record:

- The question: can this configuration return a complete, nonempty streamed response?
- Model filename, revision/hash, engine version, backend, context size, parallel slots, and cache policy.
- Whether this is the first request after startup.
- Your expectation and what would count as a protocol failure.

Use the public synthetic prompt in `prompts/short.txt`; do not put private work or personal data into a public lab report.

### 4. Capture one response

After creating `configs/environment.json` as described in Setup:

```sh
python3 -m serving_lab capture \
  --base-url http://127.0.0.1:8080 \
  --model "$LAB_MODEL" \
  --prompt-file prompts/short.txt \
  --environment configs/environment.json \
  --max-tokens 64 --temperature 0 --seed 42 \
  --requests 1 --concurrency 1 \
  --name lab01-first-request \
  --output runs/lab01-first-request.json
```

The collector refuses to overwrite an existing artifact. Give later attempts new filenames so failed and successful attempts remain distinguishable.

`max-tokens` is an output ceiling, not a promise that the model will generate that many tokens. Temperature zero and a fixed seed help control sampling settings, but do not guarantee byte-identical text across hardware, engines, versions, or scheduling conditions.

### 5. Validate and inspect

```sh
python3 -m serving_lab validate runs/lab01-first-request.json --require-live --require-success
python3 -m serving_lab summarize runs/lab01-first-request.json
```

Open the JSON as well as the summary. Locate the experiment settings, completion status, response text, measured duration, and server-reported usage if available.

The `--require-live` check rejects artifacts labeled as fixtures. It does not remotely attest which process you ran or prove the metadata is truthful. Your server logs and recorded configuration supply that context.

Without `--require-success`, the validator can accept a correctly recorded failed request: its success means the evidence is internally consistent. The extra flag above requires every request to have succeeded, which is appropriate for this first-response milestone. Capture exits with code `2` when it recorded request failures; retain that artifact rather than treating it as a missing result.

## Expected outcomes

- A ready local server advertises the intended model.
- A successful request has a nonempty visible response and valid completion evidence.
- The artifact records the configuration and client measurements.
- Missing optional provenance may produce warnings; explain or fill it in before comparing performance.
- A timeout, server error, or incomplete stream is a useful failed attempt. Retain its evidence and diagnose it; do not relabel it as successful.

There is no required sentence the model must emit and no passing latency threshold. Content correctness is a separate manual observation. One request is not a performance benchmark.

## Deliverables

- `work/lab01/report.md`: configuration, command, artifact link, response observation, any failure and resolution.
- One genuine model-run JSON artifact; retain relevant failed attempts too.
- Answers: What did the engine supply? What did the client measure? What remains unverified?

Completion requires a real model response and an explanation of the system boundary. Offline fixture tests alone do not complete this lab.

## Codex check

> Read Lab 1, my environment record, artifact, and report. Run the validator. Separate automated errors, provenance warnings, and claims requiring my observations. Do not change the reported results or claim model execution unless the evidence supports it.

Continue with [Lab 2](02-measurement.md).
