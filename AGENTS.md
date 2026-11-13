# Instructions for Codex and other coding assistants

This repository is a learning lab. Read README.md and the current lab before acting. Use Python 3.9+ and the standard library for the core toolkit.

## Teach and preserve evidence

- Start by identifying the learner's current milestone. Explain unfamiliar terms before using them. Prefer one small next step, a prediction, an observation, and a short explanation.
- Default to guided assistance. Offer hints and inspect the learner's reasoning before supplying a complete exercise solution, unless they ask for one. Implement requested infrastructure and fixes directly.
- Do not invent runs, answers, performance improvements, completion records, hardware facts, or learning progress. Keep synthetic fixtures visibly labeled. Never relabel fixture output as live evidence.
- Preserve user code, notes, raw evidence, and report edits. New experiments use new paths. Do not rewrite measurements to make tests pass.
- Distinguish validation of file structure, validation of behavior, and evaluation of a scientific claim. Unknown usage stays unknown; a streamed chunk is not necessarily one token.
- Treat benchmark expectations as hypotheses. Investigate contrary results and record confounds. Do not require exact generated wording or machine-independent speed thresholds.
- Do not alter study goals, budgets, or schedules unless requested.

## Run and review

From the repository root:

```sh
python3 -m unittest discover -s tests -q
python3 -m serving_lab validate runs/EXPERIMENT.json --require-live
python3 -m serving_lab summarize runs/EXPERIMENT.json
```

Offline tests never download models or call external services. Actual live runs require a running server and are reported separately. Read docs/verification.md before interpreting results. Add meaningful regression tests for fixes to protocol parsing, measurement, or validation. Do not add tests that merely repeat implementation constants.

## Versions and publication

- Use the pinned baseline in configs/assets.lock.json unless explicitly testing a different version; record all changes.
- Bind local servers to 127.0.0.1. Do not start cloud spending, rent accelerators, expose ports, or send prompts to hosted endpoints without a user request.
- This repository is public. Keep model weights, downloaded binaries, secrets, and raw logs in ignored paths. Review chosen submissions before publishing; use synthetic prompts.
- Do not import private job-search data, resumes, contact records, or unrelated workspace files.
- Use `codex/` for assistant-created working branches. Commit and publish only when requested or included in the task's authorized scope.

## Useful review format

State: (1) what was executed, (2) what evidence supports the result, (3) what passed or failed, (4) what remains uncertain, and (5) one next learning step. Cite the relevant artifact path. Do not equate a green test suite with completion of the learner's experiments.
