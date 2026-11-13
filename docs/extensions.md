# Extensions after the core lab

Choose one extension in response to a question from your report. These are optional projects, not prerequisites or automatic additions to your study schedule. Keep using short learning sessions and preserve a working baseline.

## A. Understand attention and build a toy cache

**Question:** What exactly is the engine reusing during generation?

**Preparation:** [3Blue1Brown's attention lesson](https://www.3blue1brown.com/lessons/attention/), followed by [Hugging Face's cache explanation](https://huggingface.co/docs/transformers/main/cache_explanation). Refresh vectors, matrix multiplication, weighted averages, and softmax as needed. Start with one attention head and one layer.

**Exercise:** Build a tiny educational causal-attention calculation using fixed, small arrays. Compare full-prefix recomputation with incremental computation that reuses earlier K/V arrays. This is a separate toy program, not a replacement for llama.cpp's production cache.

**Verification:** For the same fixed weights and input, compare corresponding numerical outputs within a documented tolerance. Test causal masking, cache growth, reset between independent requests, and an empty/initial cache. Floating-point calculations may need tolerance; matching arbitrary generated text is not the objective.

**Deliverable:** A diagram, small program, tests, and a short explanation of which computations caching avoids and which remain.

**Limit:** The exercise models an ordinary causal attention layer. Real engines may use grouped heads, sliding windows, paging, quantized caches, or architectures whose state is different. Do not generalize one toy array layout to every model.

## B. Observe prefix-cache reuse

**Question:** Does repeating a shared prefix reduce prompt-processing work in this configuration?

**Preparation:** Read the cache controls for your pinned engine version. For a later vLLM implementation, consult its [automatic prefix-caching documentation](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/).

**Exercise:** Compare documented cold/restarted runs, repeated exact prompts, and prompts with controlled shared prefixes. Hold other conditions fixed and randomize condition order where appropriate. Use engine cache/prompt metrics when exposed.

**Verification:** Validate artifacts and check the workload construction. Performance improvements are observations, not unit-test assertions. A faster second request alone cannot isolate prefix caching from other warmup effects.

**Deliverable:** A workload definition, configuration, cache evidence, and a qualified comparison.

## C. Try vLLM as a second backend

**Question:** Which observations transfer to a different serving implementation?

**Preparation:** [vLLM installation](https://docs.vllm.ai/en/stable/getting_started/installation/), [quickstart](https://docs.vllm.ai/en/stable/getting_started/quickstart/), [architecture](https://docs.vllm.ai/en/stable/design/arch_overview/), and [metrics](https://docs.vllm.ai/en/stable/usage/metrics/). Verify current hardware support before setup. Cloud compute and downloads are optional and require your own budget decision.

**Exercise:** Run the same client workload against a separately documented vLLM server. Use supported model artifacts and record the exact model revision, precision/quantization, tokenizer, chat template, backend, and engine version.

**Verification:** Reuse protocol/artifact checks. Never call a comparison “engine-only” if hardware, weights, precision, chat template, or generation settings differ. A GGUF build and another model distribution are not automatically identical implementations of the same workload.

**Deliverable:** A compatibility note and comparison that clearly names the changed variables. Running both engines simultaneously is not required.

## D. Add tracing and investigate cancellation

**Question:** Where does time accumulate, and does cancelling a request stop unnecessary server work?

**Exercise:** Add request IDs and tracing to a small gateway or client only after the direct-client baseline works. Follow the request from admission to first content and completion. Cancel a long request, then inspect server activity to determine whether work stops.

**Verification:** Unit-test context propagation, cancellation/error paths, and redaction with deterministic fixtures. Record dropped/disconnected requests distinctly. Do not infer that the engine stopped merely because the client stopped reading.

**Deliverable:** A trace, reproducible cancellation scenario, and an explanation of instrumentation overhead and gaps.

## E. Resource limits and quantization

**Question:** How do context capacity and model precision affect memory, output quality, and performance?

**Exercise:** Change one setting or artifact at a time. Compare documented context limits or two supported quantizations of the same source model. Include output-quality inspection as well as timing.

**Verification:** Record file hashes and actual configured context. Process memory can be preallocated and includes weights and other allocations; it is not a direct measurement of logical KV-cache occupancy. A smaller file does not by itself prove a smaller total runtime footprint or acceptable quality.

**Deliverable:** A memory/performance/quality tradeoff report with limitations.

## F. Make a focused open-source contribution

**Question:** Can you improve a reproducible observability, parser, cancellation, or scheduling issue?

**Exercise:** Find an existing issue or reproduce a specific behavior on a pinned revision. Read that project's contribution instructions. Prepare the smallest useful change and a regression test; an investigation or documentation correction is also a valid outcome.

**Verification:** Follow upstream tests and report exact reproduction steps. Ask before publishing comments or pull requests through an assistant. A local patch is not evidence that upstream accepted the change.

**Deliverable:** A reproducible issue description, patch or investigation, validation results, and a clear statement of publication status.

## Suggested order

For serving-platform work, tracing, cancellation, and better controlled measurements may be immediately useful. For inference-engine work, start with the toy attention/cache exercise, then study real scheduler and memory-management code. Distributed inference and GPU-kernel optimization are larger later projects; a single local benchmark does not validate them.
