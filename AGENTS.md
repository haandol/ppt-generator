# PPT Generator — Agent Guide

> Python MCP server that auto-generates presentations. LLM generation is offloaded to
> the client via a prepare/ingest handshake — the server owns prompts, output schemas,
> and deterministic post-processing (validation, layout, lint, render), not model calls.
> This file serves as a **table of contents**. See `docs/` for details.

## Project Overview

- **Tech stack**: Python 3.13+ · MCP · Pydantic (output schema + validation) · no server-side LLM
- **Distribution**: Claude Code plugin (`.claude-plugin/plugin.json`) + skills (`skills/`)
- **Package manager**: uv · Build: hatchling · Entry point: `ppt_generator.server:main`
- **ALPS design doc**: [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md)

## Repository Structure

```
.claude-plugin/plugin.json # Claude Code plugin manifest (runs the MCP server via uv)
skills/                    # ppt-outline, ppt-design, ppt-modify, ppt-visual-qa (client workflows)
src/ppt_generator/
├── server.py              # MCP server entry point
├── di/                    # Dependency injection (container — wires stateless services)
├── interfaces/            # Schemas, constants, prompts, spec_utils, handoff (prepare/ingest envelope)
├── templates/             # HTML templates, layout mapping
└── tools/
    ├── outline/           # Outline: prepare_outline / ingest_outline
    ├── design/            # Design spec: prepare_*/ingest_* (generation, modify, review)
    ├── slides/            # HTML slide rendering
    ├── visual_qa/         # Visual QA: screenshot (server) + analyze/fix (client, prepare/ingest)
    ├── pptx/              # PPTX export
    ├── pptx_import/       # PPTX import
    └── project/           # Project management
```

## LLM Offloading — prepare/ingest (Critical)

The server does not call an LLM. Every generation step is a pair:
- `prepare_*` assembles the exact system+user prompt and returns it with the output
  JSON schema (`response_schema`, from the Pydantic model's `model_json_schema()`).
- `ingest_*` validates the client-generated JSON against that same Pydantic model, then
  runs the identical post-processing (`to_dataclass` → `clean_slide_spec` → lint → render → save).

Prompts (`interfaces/prompts/`), output models (`interfaces/llm_output_models.py`), and all
post-processing stay server-side, so output is byte-for-byte what the old in-server LLM path
produced. Per-slide tools are stateless; the client drives parallelism and iteration loops
(see `skills/`). Design decision: [`docs/adr/offload/0001`](docs/adr/offload/0001-client-llm-offload-plugin.md).

## Commands

```bash
uv sync                                          # Install dependencies
uv run ppt-generator                             # Run MCP server (stdio)
uv run pytest                                    # Run all tests
uv run pytest tests/test_xxx.py::test_func -v    # Run specific test
```

## ADR-First Workflow (Required)

For any feature addition or change, **you must write/update an ADR before writing code** and get user confirmation before proceeding with implementation.

1. **Analyze**: Investigate the codebase to identify scope and impact of changes
2. **Write/Update ADR**: Organize Context, Decision, Technical Details, and Acceptance Criteria, then present to the user
3. **User Confirmation**: Get user approval on the ADR content (if changes are requested, update the ADR first)
4. **Implement**: Write code based on the approved ADR
5. **Write Tests**: Always write test code for changed functionality (details: [Testing Guide](docs/harness/testing.md))
6. **Run Tests**: Confirm all tests pass with `uv run pytest`

Without this order, users cannot anticipate what changes will occur, and course corrections after implementation waste effort.

### ADR Writing Rules

- **Update existing ADRs first**: If within scope of an existing ADR, modify that section directly. Only create a new ADR when there is no existing one to merge into
- **File location**: Under `docs/adr/` directory · **Naming**: `NNNN-<kebab-case-title>.md`
- **No code snippets or file paths**: Do not include implementation code snippets or file paths in ADRs. To avoid needing to update ADRs every time code changes, ADRs should only record "why" and "what" level design decisions, leaving "how" implementation details to the code
- ADR writing guide: [`docs/adr/README.md`](docs/adr/README.md)

## Pipeline Abstraction Levels (Critical)

Each pipeline stage has a distinct abstraction level. Stages must NOT overlap responsibilities:

| Stage | Decides | Does NOT decide |
|-------|---------|-----------------|
| **Outline** | WHAT (topics, key points) + HOW (layout direction, element count, relationships) | Colors, fonts, coordinates, exact sizes |
| **Design Spec** | WHERE (pixel coordinates) + STYLE (colors, fonts, sizes) | Content topics, element count, spatial direction |

When modifying prompts or pipeline logic:
- Never let a downstream stage re-decide what an upstream stage already determined
- Never let an upstream stage specify details that belong to a downstream stage
- If a stage needs information from another, pass it explicitly — don't duplicate the decision

## Conventions

- Type hints required (`-> None`, `-> str`, etc.)
- Constants in `interfaces/constants.py`, prompts in `interfaces/prompts/*.prompt.md`
- Korean docstrings required for MCP tool functions (exposed to clients)
- Client generation in tests is mocked at the service `ingest_*` boundary (no real LLM)
- Conventional Commits: `<type>(<scope>): <subject>` (details: [CONTRIBUTING.md](CONTRIBUTING.md))

## Verification Criteria

Always verify before completing work:

1. Do tests exist for the changed functionality?
2. `uv run pytest` passes
3. Related ADR is up to date
4. MCP client compatibility confirmed when changing existing tool signatures
5. `prepare_*`/`ingest_*` stay paired — output schema matches the validating model

## Mandatory Testing Rules

When adding or modifying features, **tests must always be written alongside the code**.

- New function/module → Add tests that verify the functionality
- Changed function behavior → Add or update tests that verify the changed behavior
- Bug fix → Write a test that reproduces the bug first, then confirm it passes after the fix
- Never commit code without tests

Details: [`docs/harness/testing.md`](docs/harness/testing.md)

## Constraints

- No major feature additions/changes without an ADR — ADR-First workflow required
- No feature additions/modifications without tests — mandatory testing rules apply
- Only bump patch version — major/minor version bumps require explicit user request
- Do not bypass git hooks with `--no-verify`
- Do not delete or modify tests to make them pass — fix the code instead
- Keep the prepare/ingest contract intact: `prepare_*` returns the prompt +
  `response_schema` (the Pydantic model's schema), and `ingest_*` validates against the
  SAME model. Prompts and output models are the source of truth — never fork them into skills.

## Approach with Caution

- `server.py` — Tool registration logic
- `di/container.py` — Dependency injection setup
- Changing existing tool signatures (affects MCP client compatibility)
- The prepare/ingest split — a prompt change in `prepare_*` without the matching schema
  in `ingest_*` breaks validation; keep them paired
- PPTX conversion logic (`tools/pptx/` — coordinate conversion, style mapping)
- HTML rendering logic (`tools/slides/html_renderer.py`)

## Detailed Documentation

| Document              | Path                                     | Description                                     |
| --------------------- | ---------------------------------------- | ----------------------------------------------- |
| Architecture          | [`docs/harness/architecture.md`](docs/harness/architecture.md) | Pipeline, Controller-Service pattern, parallel processing, token tracking, MCP tool list |
| Schemas               | [`docs/harness/schemas.md`](docs/harness/schemas.md)     | Domain models, LLM output models, component_hint table |
| Environment & Config  | [`docs/harness/environment.md`](docs/harness/environment.md) | Environment variables, models used, MCP client config examples |
| Testing               | [`docs/harness/testing.md`](docs/harness/testing.md)         | Test writing rules, patterns, checklist         |
| ALPS Design Doc       | [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md) | Feature list, functional specs, acceptance criteria |
| ADR Index             | [`docs/adr/README.md`](docs/adr/README.md) | Full ADR list and writing guide                 |
