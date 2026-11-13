# Working through the lab with Codex

Open this repository's directory as your project. The repository's AGENTS.md describes the tutoring and evidence rules. These are prompts for collaboration, not a claim about a particular Codex UI feature.

## Before an exercise

> Read AGENTS.md and Lab 00. Assume I know HTTP and programming but not neural networks. Help me complete only the first milestone. Explain each new term and ask me to predict what will happen before running an experiment.

## When stuck

> Read my command, output, and work/lab01/notes.md. Diagnose the failure using the pinned setup. Give me the smallest useful fix and explain why it works. Preserve existing evidence and do not download a different model silently.

## Reviewing measurements

> Review submissions/lab03/report.md against the raw JSON evidence it cites. Run the offline tests and artifact validator. Check whether I changed one variable, separated warmups, counted tokens correctly, retained failures, and overstated causality. Explain any disagreement with the evidence. Do not rewrite my observations.

## Reviewing code

> Review my capstone implementation. Focus on incorrect timestamp semantics, concurrency accounting, cancellation and failure behavior, and tests that would catch a real regression. Help me reason through one issue at a time.

## Completion standard

A useful assistant can check files and calculations, reproduce commands, and challenge explanations. It cannot establish that you understand a concept just because code passes. End each lab by explaining the central concept in your own words and interpreting one result without the assistant drafting your answer.

Keep assistance transparent in reports: list what you wrote, what an assistant generated, and what you personally verified. You may ask for more direct implementation help whenever that serves your learning goal.
