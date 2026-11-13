# Lab 3 — Prompt length and generation length

**Estimated effort:** 120–180 minutes, including interpretation and repetitions.

## Goal and outcomes

Design small controlled comparisons and distinguish an observation from an explanation. You will learn the operational roles of prefill and decode, how caching complicates experiments, and why expected performance trends are hypotheses rather than grading rules.

## Prerequisite learning

Complete [Lab 2](02-measurement.md). Read the prefill/decode discussion in [NVIDIA's inference-optimization introduction](https://developer.nvidia.com/blog/mastering-llm-techniques-inference-optimization/). Focus on the two phases; defer GPU kernels, quantization mathematics, and model parallelism.

For an ordinary causal text-generating transformer:

- **Prefill** processes the prompt and builds intermediate state used to predict the first output token.
- **Decode** repeatedly processes newly generated tokens, reusing earlier state to predict subsequent tokens.
- The engine's **KV cache** retains reusable intermediate attention data. It is provided by the engine.

These descriptions explain the conceptual phases. Client first-content time also includes other work and is not a pure prefill timer.

## Design rules

Before each experiment, write the question, independent variable, controlled settings, repetitions, expected trend, and at least one alternative explanation. Keep engine/model/backend, sampling settings, server slots, and hardware conditions fixed unless they are the variable under study.

Record the prefix-cache policy. If you cannot verify that reuse is disabled, say **reuse allowed or unknown**. Resetting a client does not reset the server's cache. Changing a seed does not reliably prevent prefix reuse. Different prompt contents also change the workload; this is a limitation of the comparison.

Keep first-after-restart measurements separate from repeated-prompt measurements. Restarting can affect several forms of state, so a first-after-restart measurement is not a perfect isolated measurement of KV caching.

## Experiment A — Change input length

### Question

With the same output ceiling, how do client latency and server prompt-processing measurements differ between short and long inputs?

### Steps

1. Inspect `prompts/short.txt` and `prompts/long.txt`. Record the intended difference, the requested task, and any semantic differences that could affect output.
2. Ensure the context configuration can accommodate the full input plus output. Use server-reported prompt-token counts when available; character length is not a token count.
3. Record whether this is a warmed, repeated-prompt experiment or a first-after-restart experiment. The commands below intentionally collect a **warmed/repeated-prompt** condition; their settings alone do not disable cache reuse.
4. Capture both conditions:

```sh
python3 -m serving_lab capture \
  --model lab-model --prompt-file prompts/short.txt \
  --environment configs/environment.json \
  --max-tokens 64 --temperature 0 --seed 42 \
  --requests 8 --concurrency 1 --name lab03-short-rep1 \
  --output runs/lab03-short-rep1.json

python3 -m serving_lab capture \
  --model lab-model --prompt-file prompts/long.txt \
  --environment configs/environment.json \
  --max-tokens 64 --temperature 0 --seed 42 \
  --requests 8 --concurrency 1 --name lab03-long-rep1 \
  --output runs/lab03-long-rep1.json
```

5. Repeat the pair with new filenames for `rep2` and `rep3`. Alternate which condition runs first to expose order effects. Keep failed attempts and note background activity or thermal changes.
6. Validate and summarize the artifacts, then compare first-content time, request duration, actual output length when reported, and failures. Preserve the run labels rather than pooling all conditions into one distribution.

```sh
python3 -m serving_lab validate runs/lab03-*-rep*.json --require-live
python3 -m serving_lab summarize runs/lab03-*-rep*.json \
  --output runs/lab03-input-summary.md
```

### Expected observations

Without reuse, longer prompts generally require more prompt processing. Your client result may not rise monotonically because of reuse, implementation details, output variation, scheduling, or measurement noise. A flat or reversed result does not fail the lab. It requires a careful explanation of what was actually measured.

### Optional stricter follow-up

Collect one request after each documented server restart for each input, repeating several times and alternating order. Label these separately as first-after-restart observations. If the engine offers a verified way to control prefix reuse, repeat with that policy and record its exact setting. Do not assert that all other cold/warm effects have disappeared.

## Experiment B — Change the generation budget

### Question

How does allowing a longer answer change actual generated length and completion time?

### Steps

1. Inspect `prompts/generate.txt`. It requests enough output that the ceilings can matter, but the model may still stop early.
2. Run conditions with `--max-tokens 32`, `64`, and `128`, keeping the same prompt and other settings. Use the capture command above with `--prompt-file prompts/generate.txt`, eight sequential requests, and distinct names such as `lab03-output32-rep1`.
3. Repeat the three conditions with new filenames. Rotate their order across repetitions.
4. Compare actual completion tokens, completion reason, first-content time, total duration, and failures. Report missing usage as unknown.

### Expected observations

A larger ceiling permits more decode work but does not force it. Early stopping can make two budgets produce similar actual lengths. Claims about the relationship between decode length and time should use observed token counts when available, not just the configured ceiling.

## Questions for the report

1. What did you measure directly, and what did you infer about prefill or decode?
2. Did every request have the same actual output length? How does that affect the comparison?
3. What evidence supports your cache-policy description?
4. Did the condition order matter?
5. What one follow-up experiment would best separate your leading explanation from an alternative?

## Deliverables and grading criteria

Submit `work/lab03/report.md`, the run artifacts, and generated summaries. A successful submission has stated hypotheses, repeatable settings, multiple observations, retained failures, and qualified conclusions. It is not graded on whether longer inputs or outputs always took longer.

If an experiment is too slow on your machine, reduce the request count consistently across compared conditions and document the change. Do not quietly remove inconvenient samples.

Continue with [Lab 4](04-concurrency.md).
