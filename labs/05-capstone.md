# Lab 5 — Produce a defensible engineering report

**Estimated effort:** 90–180 minutes after the experiments. A deeper follow-up is optional.

## Goal

Turn observations into a reproducible engineering argument. The final result should allow another person—or Codex in a new workspace—to understand what ran, check the artifacts, and distinguish evidence from assumptions.

You will practice experiment provenance, bounded conclusions, verification, and explaining a serving system without overstating your level of model-engine expertise.

## Prerequisites

Complete the core outcomes of Labs 0–4. If you skipped or reduced an experiment, report that explicitly. Use [the report template](../templates/report.md) and your preserved artifacts.

## Procedure

### 1. Inventory the evidence

List each run's filename, purpose, model/engine identifiers, condition, and live/fixture status. Include failed or interrupted runs where they affect the interpretation.

Do not put downloaded model weights, credentials, private prompts, or machine-specific sensitive logs in the submission. Share small, reviewed artifacts and the instructions needed to regenerate them. Record limitations if some evidence must remain local.

### 2. Verify the instruments and artifacts

```sh
python3 -m unittest discover -s tests -v
python3 -m serving_lab validate runs/lab01-first-request.json --require-live --require-success
python3 -m serving_lab validate runs/lab02-baseline.json --require-live --require-success
python3 -m serving_lab validate runs/lab03-*-rep*.json --require-live
python3 -m serving_lab validate runs/lab04-rep*/*.json --require-live
```

Adjust explicit paths to the files you actually created. A missing group is not completed work. Record the command, outcome, and any remaining warnings in your final report.

Without `--require-success`, an artifact can pass validation while containing failed requests, because correctly recording a failure is valid evidence. The stricter flag is used for the first-response and successful-baseline milestones above. Keep default validation for experiments that deliberately investigate errors. Capture returns exit code `2` when requests fail; ordinary validation returns a nonzero exit code for invalid evidence, and `--require-success` additionally rejects recorded request failures.

Three different checks are involved:

| Check | What it establishes | What it does not establish |
|---|---|---|
| Offline unit tests | Collector/parser/validator behavior for controlled cases | Real model execution or deployment performance |
| Artifact validation | Internal structural and numerical consistency; fixture distinction when requested | Truth of manually supplied provenance, semantic answer quality, or causal interpretation |
| Human/Codex evidence review | Whether claims cite observations and acknowledge limits | Guaranteed correctness, model expertise, or production readiness |

### 3. Write the explanation

Create `submissions/final-report.md`. Include:

1. **System:** one diagram showing model, engine, server, client, and measurement boundary.
2. **Question:** one or two concrete performance or behavior questions.
3. **Method:** controlled variables, changed variables, condition order, repetitions, startup/cache policy, and hardware/software versions.
4. **Results:** actual data with counts, failures, and correct units. Cite artifact paths next to claims.
5. **Interpretation:** measured facts, inferred explanations, alternative explanations, and what remains unknown.
6. **Reproduction:** exact commands and metadata needed to repeat the work; do not require exact generated text or latency.
7. **Reflection:** explain prefill, decode, batching, and the cache's purpose at the level you understand. List open questions honestly.

### 4. Add one small, tested extension and a recommendation

Implement one small utility or improvement under `work/capstone/`, or make a focused change to the supplied toolkit. Choose something motivated by your results:

- A comparison utility that refuses to compare runs whose model hashes or backends differ without labeling the difference.
- An analysis function that reports the spread of client latency per condition while retaining failures and missing usage.
- A clearer report view that separates first-after-startup observations from repeated-prompt observations.

Write at least one meaningful regression test using synthetic records with known expected behavior, plus a boundary or failure case. Include the test command in the report. The test should verify the analysis or accounting rule, not require a particular real-model response or a fixed runtime speed. Label synthetic fixtures clearly. A small function that you can explain is sufficient; do not add a second server or a cache implementation merely to increase project size.

Then make one evidence-based recommendation: keep concurrency at a tested level for a particular local workload, add a missing measurement, or control prefix reuse before attempting a stronger inference. A justified recommendation to collect more data is acceptable.

If you change a server setting, repeat the relevant workload using fresh artifact names. Keep a baseline so the before/after claim is reviewable.

### 5. Prepare a reviewed submission

Keep working notes and code in `work/` and raw captures in ignored `runs/`. Choose the small artifacts needed to support the final report and copy them into `submissions/`, following that directory's README. Update report links to the selected evidence so a fresh clone can follow the argument. Check that copied values match the originals; do not edit measurements during curation. Keep excluded raw files locally and explain exclusions that affect the analysis.

### 6. Review with Codex

Suggested prompt:

> Review this lab submission using AGENTS.md and the Lab 5 rubric. Run the offline tests and validate the listed artifacts. Check every result claim against its source artifact. Identify fixture-only evidence, missing provenance, misleading token metrics, confounded comparisons, and unsupported causal claims. Distinguish failures from warnings. Do not edit measured data, invent observations, or mark my unanswered learning questions complete.

Treat its review as assistance. Read the proposed corrections and confirm that they describe your actual work before publishing.

## Suggested rubric

| Area | Points | Evidence |
|---|---:|---|
| Reproducible setup and provenance | 20 | Exact assets/configuration; hardware/backend; clear cache/startup policy |
| Measurement correctness | 25 | Correct client-versus-engine boundary; chunks versus tokens; missing usage handled honestly |
| Experimental design | 20 | Controlled comparisons, repetitions, condition order, retained failures |
| Interpretation | 25 | Claims linked to data, limitations and alternatives, no required performance trend |
| Report, code, and verification | 10 | Small explainable extension, meaningful tests, clear instructions, recorded validation outcomes |

Scores support self-review; the automated tools do not award this rubric. Perfectly repeatable generated text, low latency, or a dramatic speedup earns no points by itself.

## Completion statement

A supported outcome is: “I operated a local LLM-serving system, measured streamed requests, studied prompt/output length and concurrency, and documented the limits of my results.”

This lab alone does not establish production model-serving ownership or expertise in attention kernels, GPU scheduling, or distributed inference. Explore those deliberately through [the extension guide](../docs/extensions.md).
