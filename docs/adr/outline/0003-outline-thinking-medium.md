# Enable Medium Thinking for Outline Generation

## Status

Accepted

## Context

Outline generation is a critical first step that determines the overall structure and quality of the entire presentation. Previously, the outline model was called without extended thinking, while the design spec model already used adaptive thinking. Since the outline directly influences all downstream steps (script, design spec), investing more reasoning effort at this stage has outsized returns.

## Decision

Enable `thinking: adaptive` with `output_config.effort: "medium"` for the outline generation model, on both Bedrock and Anthropic providers.

## Changes

- `src/ppt_generator/di/model_factory.py`: Added `thinking_effort` parameter to `create_bedrock_outline_model()` and `create_anthropic_outline_model()`. When provided, sets `thinking: {type: adaptive}` and `output_config: {effort: <value>}`. For Anthropic, the `output_config` correctly merges `effort` and `format` (json_schema) fields.
- `src/ppt_generator/di/container.py`: Pass `thinking_effort="medium"` when creating the outline agent.

## Consequences

- Outline generation will use extended thinking at medium effort, improving structure quality.
- Slightly increased latency and token usage for outline generation.
- Script generation remains unchanged (no thinking) as it is a simpler text generation task.
