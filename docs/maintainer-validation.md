# Initial toolkit validation

Checked on 2026-11-12 (America/Los_Angeles). This records preparation of the lab kit, not completion of the learner's labs.

## Executed

- `python3 -m unittest discover -s tests -q`: **50 tests passed** on the initial local macOS ARM64 setup. The current CI run is the authority for later revisions and platforms.
- Official macOS ARM64 llama.cpp b12110 archive downloaded and matched the pinned size and SHA-256.
- The asset helper extracted the real archive, including its shared-library symlink chains.
- `.tools/llama/llama-server --version` ran successfully and reported `0.9.0-dev`, build `12110`, commit `cd959bae9`.
- The documented server flags were found in that binary's `--help` output.
- Relative documentation links were checked for existing targets.
- Offline HTTP fixtures exercised capture, validation, summaries, failure handling, and fixture rejection. These are synthetic tests.

## Not executed

No pretrained weights were downloaded during initial kit validation. No real-model request, throughput measurement, latency result, GPU-memory experiment, or vLLM deployment is represented as completed. Ubuntu/Intel binaries and the source-build fallback were not executed locally. Model/release pins came from official upstream metadata; learner setup verifies the downloaded bytes before use.

Record actual model experiments separately under the lab instructions. Do not use this page as evidence that a student completed Lab 1 or later labs.
