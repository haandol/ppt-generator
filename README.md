# PPT Generator

An MCP (Model Context Protocol) server that automatically generates presentations from a given topic using AI.

### Cost & Time

> Based on Claude Sonnet 4.6 + Bedrock. Time and cost scale proportionally with slide count and complexity.

**5-slide benchmark (Outline → Script → Design, excluding Visual QA)**

| Stage | Input | Output | Cache Write | Cache Read | Cost (USD) |
| --- | --- | --- | --- | --- | --- |
| Outline + Script | 4K | 3K | - | - | $0.12 |
| Design (summary + slides) | 4K | 70K | 31K | 29K | $1.17 |
| **Total** | **8K** | **73K** | **31K** | **29K** | **~$1.3** |

Visual QA does not run automatically and must be explicitly requested by the user. To reduce costs, set `max_iterations=1` or request Visual QA only for specific problematic slides.

## Prerequisites

1. Python 3.13+
2. [uv](https://docs.astral.sh/uv/) package manager
3. AWS CLI configured (default: Bedrock IAM) or Anthropic API Key

## 1. Installation

```bash
git clone https://github.com/haandol/ppt-generator.git
cd ppt-generator
uv sync
```

## 2. Register MCP Server

Add the server to your MCP client configuration file.

**Claude Code** — create `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"]
    }
  }
}
```

**Kiro** — create `.kiro/settings/mcp.json` at the project root:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"]
    }
  }
}
```

**Claude Desktop** — add the same format to `claude_desktop_config.json`.

> By default, IAM credentials from the AWS CLI profile are used (Bedrock). To use the Anthropic API, add `"ANTHROPIC_API_KEY": "sk-ant-..."` to the `env` section.

> Replace `/path/to/ppt-generator` with the actual project path.

### LLM Providers

Supports both Anthropic API and AWS Bedrock.

| Provider               | Required Environment Variables                              |
| ---------------------- | ----------------------------------------------------------- |
| Bedrock IAM (default)  | AWS CLI profile or `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |
| Bedrock (Bearer Token) | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`                    |
| Anthropic              | `ANTHROPIC_API_KEY`                                         |

When `LLM_PROVIDER` is not set, it auto-selects `anthropic` if `ANTHROPIC_API_KEY` is present, otherwise defaults to `bedrock`.

> For the full list of environment variables and detailed client configurations, see [docs/architecture.md](docs/architecture.md).

## 3. Usage

### Step 1 — Generate or Import PPT

**Create new** — Prepare your content in a file like `context.md`, then request via your MCP client:

```
Read @context.md and generate a PPT using ppt-generator.
```

**Import existing PPTX** — You can also import an existing PPTX file for editing:

```
Import @presentation.pptx using import_pptx.
```

Importing automatically generates an HTML preview. You can skip Step 2 and directly use per-slide editing, Visual QA, and export features. Parsing is deterministic with no LLM calls, so no additional cost is incurred.

### Step 2 — Provide Project Information

Before outline generation, you will be asked for the following:

- **Presentation purpose** — e.g., "internal tech sharing", "client proposal", "conference talk"
- **Presentation duration** — 3–60 minutes (default: 15 minutes)
- **Audience type** — `general` / `technical` / `executive`

The system then auto-generates in order: Outline → Script → Design Spec. You get a chance to review and edit at each stage.

### Step 3 — Edit Individual Slides (Optional)

After design spec generation (or PPTX import), you can modify individual slides. Instead of regenerating everything, you can add, update, or delete specific slides:

```
Add a bar chart comparing performance data below the diagram on slide 3.
Slide 5 has too much text — reduce it to key bullet points with icon layout.
Add a Q&A slide after slide 7.
```

### Step 4 — Visual QA (Optional)

Automatically detects and fixes visual defects (line breaks, overlaps, margin misalignment, etc.). **Does not run automatically — must be explicitly requested by the user.**

**Prerequisites:**

```bash
uv sync --group visual-qa
playwright install chromium
```

```
Run visual_qa.
```

> Visual QA is an opt-in tool. A suggestion message appears after design spec generation, but it will not run until explicitly requested. If Playwright is not installed, it can be skipped without affecting existing functionality.

### Step 5 — Export Files

Once design spec generation is complete, an HTML file is automatically exported by default. If it was not exported automatically, you can request it manually:

```
Export as HTML and open it.
```

To export in PPTX format:

```
Export as PPT and open it.
```

## Debug Logging

The MCP server uses stdio communication, so stdout logs cannot be viewed directly. Enable file logging to write debug-level logs to a file.

### Configuration

Add `PPT_LOG_DIR` to the `env` section when registering the MCP server:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "PPT_LOG_DIR": "/tmp/ppt-generator"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description |
| --- | --- |
| `VISUAL_QA_PARALLEL` | Number of parallel workers for Visual QA (default: 8) |
| `VISUAL_QA_MAX_ITERATIONS` | Maximum fix iterations for Visual QA (default: 2) |
| `PPT_LOG_DIR` | Directory for per-project log files (recommended). e.g., `/tmp/ppt-generator` |
| `PPT_LOG_FILE` | Single log file path (legacy). Ignored when `PPT_LOG_DIR` is set |

- Log files rotate at 10MB with 2 backups retained.
- When `PPT_LOG_DIR` is set, a `<project_id>.log` file is created for each project.

### Viewing Logs

```bash
# View logs for a specific project
tail -f /tmp/ppt-generator/<project_id>.log

# View all logs
tail -f /tmp/ppt-generator/*.log
```

## Development

```bash
uv run ppt-generator          # Run MCP server (stdio mode)
uv run pytest                  # Run all tests
```

## Documentation

- [Architecture](docs/architecture.md) — Feature details, MCP tool list, workflows, project structure, tech stack
- [ALPS Design Document](docs/ppt-generator.alps.md)
- [ADR](docs/adr/) — Architecture Decision Records
- [Contributing Guide](CONTRIBUTING.md)
