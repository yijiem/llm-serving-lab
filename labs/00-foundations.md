# Lab 0 — The minimum foundations

**Estimated effort:** 60–90 minutes, split into 30-minute sessions. This is a preparation guide, not an exam in neural-network mathematics.

## Purpose

Establish enough vocabulary to run an existing language model and describe what happened. You are not expected to train a model, implement attention, or build a KV cache before starting Lab 1.

By the end, you should be able to:

- Distinguish a pretrained model, an inference engine, an HTTP server, and a client.
- Explain training versus inference and prompt versus generated output.
- Explain why a token is not always a word and why one streamed network chunk is not necessarily one token.
- Identify which questions belong to operating a service and which require deeper model knowledge.

## Prerequisites

Comfort with a terminal, basic Python or another programming language, HTTP, and files. The core lab uses Python 3.9+ and its standard library. No calculus, PyTorch, CUDA, or prior ML course is required for the first experiment.

## Read or watch

Do these in order. Take notes in [the prelab template](../templates/prelab.md), using your own words.

1. **Optional orientation:** [Google Introduction to Machine Learning](https://developers.google.com/machine-learning/intro-to-ml), advertised as a 20-minute introduction. Use it if the distinction between learning parameters and writing program rules is unfamiliar.
2. **Required first pass:** [3Blue1Brown: But what is a neural network?](https://www.3blue1brown.com/lessons/neural-networks/). Focus on inputs, outputs, layers, and weights. You may defer the calculations.
3. **Required selected first pass:** [3Blue1Brown: Transformers, the technology behind LLMs](https://www.3blue1brown.com/lessons/gpt/). Focus on the opening overview, tokens, numerical representations, and repeated next-token prediction. You can return to matrix details later.

These are learning resources, not exact prerequisites imposed by an employer. Understanding every section is not a gate to Lab 1.

## The working model for this course

A pretrained model includes learned numerical parameters, usually called **weights**. **Inference** uses those existing parameters to calculate outputs. A text-generating model repeatedly produces scores for possible next tokens; a generation procedure chooses a token, adds it to the sequence, and continues.

| Component | Its job | What we use |
|---|---|---|
| Model and tokenizer | Learned parameters and the rules for representing text as token IDs | A small pretrained Qwen instruct model supplied in GGUF format |
| Inference engine | Execute the model and manage its working memory | llama.cpp |
| Server | Accept requests and deliver results over HTTP | llama.cpp's existing server |
| Experiment client | Send requests and record observations | The repository's Python tools, with optional student extensions |

The engine already handles the KV cache and request scheduling. Your initial project is to operate, observe, and investigate that implementation.

## Prelab exercises

1. **Draw the boundaries.** Draw client → server → engine/model and the response path. Name one failure that could occur at each boundary.
2. **Explain the words.** In one sentence each, explain model, weight, inference, token, prompt, and stream. Mark anything you are unsure about rather than guessing.
3. **Predict a measurement.** Suppose one request produces a short answer and another produces a much longer answer. What could you measure at the client? Which part of the server would remain invisible from those measurements alone?
4. **Separate two claims.** Explain why “the request returned successfully” and “the answer was factually correct” require different evidence.

## What can wait

You do not need Q/K/V equations to get a response or measure request time. Later experiments motivate these concepts:

| Observation | Concept to learn next |
|---|---|
| An initial delay before visible text | Prompt processing, often called prefill, plus queueing and transport |
| Text continues arriving | Decode and streaming |
| Several active requests share resources | Scheduling and batching |
| Long contexts increase working-memory demand | KV-cache capacity and attention |

For ordinary causal transformer generation, the KV cache retains intermediate attention keys and values from processed tokens. It saves recomputation; it does not store a complete answer to every prompt. You may treat that as a high-level description for now. Models with other architectures or specialized cache policies can behave differently.

## Deliverable and completion criteria

Create `work/prelab.md` from the template. Include your diagram, six definitions, measurement prediction, and open questions.

You are ready for Lab 1 when you can explain the component boundaries and training versus inference. Q/K/V uncertainty is acceptable at this stage. There is no automated test for conceptual understanding; Codex can ask follow-up questions, but passing software tests does not certify your answers.

## Working with Codex

Suggested prompt:

> Read Lab 0 and my prelab notes. Ask me one question at a time about model, engine, server, and client. Explain unfamiliar terms with a small example. Do not mark an answer complete until I have explained it in my own words.

Continue with [Lab 1](01-local-serving.md).
