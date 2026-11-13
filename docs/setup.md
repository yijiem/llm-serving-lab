# Setup: one model, one engine

The core path uses **llama.cpp b12110** and **Qwen2.5-0.5B-Instruct, Q4_K_M GGUF**. A model is the learned numerical weights; llama.cpp is software that executes them. `llama-server` wraps that execution in an HTTP service. Your Python client drives experiments and records observations. The engine allocates and manages the KV cache for you.

## 1. Check the host

From the repository root:

```sh
python3 -m serving_lab doctor
python3 -m unittest discover -s tests -q
```

Use Python 3.9 or newer. If Python or Git is missing, install them through your operating system's standard developer tooling before continuing. The lab client uses only the Python standard library. The tests use a local synthetic HTTP server and do not perform model inference.

The easiest starting point is a Mac with Apple Silicon. The helper also includes pinned macOS Intel and Ubuntu x86-64/ARM64 binaries. Ubuntu binaries may require compatible system libraries; other Linux distributions and operating systems should use the source-build fallback below. A small model does not guarantee a particular speed. Allow approximately 2 GB of disk headroom for downloads and tooling and several GB of available memory; runtime allocation depends on context, parallelism, and backend. Close unrelated heavy work while benchmarking.

## 2. Download the pinned engine

```sh
python3 tools/fetch_assets.py engine
.tools/llama/llama-server --version
```

The helper downloads from the [official b12110 release](https://github.com/ggml-org/llama.cpp/releases/tag/b12110), checks its byte count and SHA-256 against [the lock file](../configs/assets.lock.json), and extracts into ignored `.tools/`. It preserves the archive's shared libraries. It refuses to replace an existing engine directory. No administrator access or system-wide installation is needed.

On a supported Mac this uses the official prebuilt binary, so Homebrew and CMake are not prerequisites. If macOS blocks execution, inspect the official source and use the OS's normal approval flow or build from source; do not disable system security protections. A hash mismatch is a stop condition, not a reason to remove verification.

## 3. Download the pretrained model

```sh
python3 tools/fetch_assets.py model
```

This explicitly downloads approximately **491 MB** to ignored `models/`. The pinned model revision is `9217f5db79a29953eb74d5343926648285ec7e67`, filename `qwen2.5-0.5b-instruct-q4_k_m.gguf`. The helper validates the complete file. Re-running the model command verifies an existing file rather than replacing it.

Read the [official Qwen model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF). The model is Apache-2.0 licensed; llama.cpp uses its own MIT license. Neither artifact is bundled in this repository. GGUF is a model storage format. Q4_K_M is a quantization scheme that reduces weight storage precision and size; it is not a different serving protocol. The small model is selected for accessible systems experiments, not answer quality.

## 4. Start the server

In **terminal A**, on Apple Silicon:

```sh
.tools/llama/llama-server \
  --model models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --alias lab-model \
  --host 127.0.0.1 --port 8080 \
  --ctx-size 8192 --parallel 4 \
  --n-gpu-layers 99 --metrics
```

For the CPU path, use the same command with `--n-gpu-layers 0`. On macOS Intel, begin with that CPU path. Keep the process running while terminal B runs clients; stop it with Ctrl-C when finished. Startup may print considerable diagnostic output. Wait until model loading completes and the service is ready.

| Option | Why it is set |
| --- | --- |
| `--model` | Exact weight file to execute |
| `--alias lab-model` | Stable API model name independent of the filename |
| `--host 127.0.0.1` | Local-only listener |
| `--port 8080` | Matches client defaults |
| `--ctx-size 8192` | Explicit context budget; inspect logs for effective per-slot limits |
| `--parallel 4` | Up to four server request slots; keep fixed during client concurrency sweeps |
| `--n-gpu-layers 99` | Requests offload of all available layers on this small model; confirm actual backend/offload in logs |
| `--metrics` | Exposes server metrics for optional investigation |

Do not assume four slots each get 8192 tokens. Context allocation and sharing are engine/version dependent. Check startup logs; keep each prompt plus generated output within the effective limit. If memory is insufficient, reduce context or parallelism, record the change, and use that same configuration for all compared conditions. Do not quietly mix baselines.

The pinned [server documentation](https://github.com/ggml-org/llama.cpp/blob/b12110/tools/server/README.md) is the authority for flags and endpoints. Request/prefix reuse is left at the engine default. This lab does **not** claim caches are disabled. A first request after process restart and a repeated warm request are different conditions; neither is automatically a pure prefill benchmark.

## 5. Record the actual configuration

In **terminal B**, from the repository root:

```sh
cp configs/environment.example.json configs/environment.json
python3 -m serving_lab check-server
```

Edit `configs/environment.json` before measuring. Confirm engine version, model hash, backend, context, and slots against the actual download and process logs. Replace `hardware` with a non-sensitive description such as chip/CPU model and RAM size (no serial numbers or hostnames). Replace `backend` with the observed backend, and describe warmup and reuse policy honestly. Remove the example note once the record reflects reality. Example settings are not evidence that your process used them.

`check-server` should list `lab-model`. If it lists another ID, verify you started the intended process before passing that ID to the client. An occupied port may be serving an unrelated model. You may choose another local port, but pass the matching `--base-url http://127.0.0.1:PORT` on every client command.

For the very first request, set `warmup_policy` to `first request after this process start; no deliberate warmup`. Later labs specify warmups separately. Warmup files are retained but excluded from measured trials.

## 6. Capture one successful request

```sh
python3 -m serving_lab capture \
  --model lab-model --prompt-file prompts/short.txt \
  --environment configs/environment.json --output runs/first.json
python3 -m serving_lab validate runs/first.json --require-live --require-success
python3 -m serving_lab summarize runs/first.json
```

Expect one completed streamed response and readable JSON evidence. Wording, speed, and token count can vary. If output already exists, choose another path. If the engine reports token usage, the summary can calculate aggregate throughput; otherwise it reports it as unknown. Inspect warnings rather than replacing missing data with estimates.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Connection refused | Server still loading, stopped, or listening on a different port |
| Wrong model ID | `check-server` output, alias, and whether an older process owns the port |
| Missing dynamic library / unsupported instruction | Binary/OS/CPU compatibility; use a compatible source build |
| Context-limit error | Effective per-slot context and actual prompt usage; reduce prompt or adjust baseline |
| Out of memory | Lower context/slots or use CPU; record the new condition |
| No usage in stream | Backend compatibility; preserve unknown counts and inspect the pinned server API |
| Truncated stream / timeout | Retain failed evidence; inspect server logs and timeout before retrying into a new file |
| Hash mismatch | Stop and compare official release metadata; never accept an unverified replacement |

## Source-build fallback

This path requires a C/C++ toolchain and CMake. Consult the official [build guide at the pinned revision](https://github.com/ggml-org/llama.cpp/blob/b12110/docs/build.md) for platform packages and backend options. From the lab root, after obtaining those prerequisites:

```sh
git clone --branch b12110 --depth 1 https://github.com/ggml-org/llama.cpp.git .tools/llama-src
cmake -S .tools/llama-src -B .tools/llama-src/build -DCMAKE_BUILD_TYPE=Release
cmake --build .tools/llama-src/build --config Release --target llama-server -j 2
.tools/llama-src/build/bin/llama-server --version
```

Use that resulting executable in the server command and record compiler/backend/build details in `notes`. Do not run the binary helper over an existing custom build. Windows learners can use WSL2 with compatible Ubuntu tools or adapt the official Windows build; this lab's shell examples use POSIX syntax. A locally built engine is a documented variant, not bitwise identical to the pinned release binary.

## Optional vLLM path

Complete the core llama.cpp sequence first. If exploring vLLM later, follow its [official installation and quickstart](https://docs.vllm.ai/en/stable/getting_started/quickstart/) for your backend. vLLM has multiple hardware backends and plugins; compatibility is version-specific. It is not a prerequisite and no paid resource is required by this course. Record the exact vLLM/model/tokenizer versions and precision. Comparing a GGUF quantized model with different weights or precision does not isolate the engine's effect.
