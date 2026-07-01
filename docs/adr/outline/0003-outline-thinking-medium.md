# Enable Medium Thinking for Outline Generation

## Status

Superseded by [offload/0001](../offload/0001-client-llm-offload-plugin.md)

Outline 생성의 LLM 호출이 클라이언트로 오프로딩되면서 서버가 모델·thinking effort 를
고르지 않게 되었다. 아래에서 언급하는 모델 팩토리(`create_*_outline_model`)는 제거되었고,
어떤 모델·thinking 설정으로 생성할지는 이제 클라이언트가 결정한다. 아래는 오프로딩
이전의 기록이다.

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
