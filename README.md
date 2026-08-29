# PPT Generator

An MCP (Model Context Protocol) server that automatically generates presentations from a given topic.

**LLM generation is offloaded to the client.** The server owns the prompts, the output
JSON schemas, and all deterministic post-processing (validation, layout, lint, HTML/PPTX
render); it never calls a model itself. Each generation step is a `prepare_*` /
`ingest_*` pair — `prepare_*` hands the client the prompt + schema, the client generates
the JSON, and `ingest_*` validates and post-processes it. This means **no AWS/Anthropic
credentials and no per-call model cost on the server side** — the client's own model does
the generating. See the ADR index under [`docs/adr/`](docs/adr/) for the design rationale.

## Prerequisites

1. Python 3.13+
2. [uv](https://docs.astral.sh/uv/) package manager
3. [Claude Code](https://claude.com/claude-code) (recommended — the plugin bundles the MCP server + workflow skills). Any MCP client that can generate JSON also works — no model API keys needed on the server.

## 1. Install as a Claude Code plugin (recommended)

The repo ships as a Claude Code plugin (manifest at `.claude-plugin/plugin.json`) that
registers the MCP server and the `ppt-outline` / `ppt-design` / `ppt-modify` /
`ppt-visual-qa` skills which drive the prepare→generate→ingest workflow.

Add the marketplace and install the plugin from within Claude Code:

```
/plugin marketplace add haandol/ppt-generator
/plugin install ppt-generator@ppt-generator
```

The plugin runs the MCP server via `uv run` against the plugin's own checkout
(`${CLAUDE_PLUGIN_ROOT}`), so `uv` must be on your `PATH` and the plugin's dependencies
must be synced. If the server fails to start, sync deps once from the plugin directory:

```bash
uv sync   # run inside the installed plugin's directory
```

> No model API keys are required — the client supplies the generation.

### Alternative — clone and register the MCP server directly

If you are not using the Claude Code plugin system (e.g. Kiro / Claude Desktop, or you
prefer a local clone), clone the repo and register just the MCP server:

```bash
git clone https://github.com/haandol/ppt-generator.git
cd ppt-generator
uv sync
```

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

> Replace `/path/to/ppt-generator` with the actual project path. This registers the MCP
> server only; the workflow skills are Claude Code plugin skills.

### Use it as a skill in Kiro / Codex

The workflow is just the MCP server plus the `prepare_*`/`ingest_*` handshake, so any
MCP client that can generate JSON can drive it — including **Kiro** and **Codex**. The
repo ships the entry points each harness loads automatically (Kiro steering at
`.kiro/steering/ppt-generator.md`, Codex guidance in `AGENTS.md`), so you get the same
skill-level guidance without duplicating the prompts.

First clone and sync once (no model API keys needed):

```bash
git clone https://github.com/haandol/ppt-generator.git
cd ppt-generator
uv sync
```

**Kiro** — copy the bundled example and fix the path, then Kiro auto-loads the steering:

```bash
cp .kiro/settings/mcp.json.example .kiro/settings/mcp.json
# edit .kiro/settings/mcp.json → replace /path/to/ppt-generator with your clone path
```

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "disabled": false,
      "autoApprove": ["export_html", "load_project_status", "list_projects"]
    }
  }
}
```

Use `~/.kiro/settings/mcp.json` instead for a global (all-workspace) registration.

**Codex** — register the MCP server via CLI or `~/.codex/config.toml`:

```bash
codex mcp add ppt-generator -- uv --directory /path/to/ppt-generator run ppt-generator
```

```toml
# ~/.codex/config.toml
[mcp_servers.ppt-generator]
command = "uv"
args = ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"]
```

Codex reads the repo's `AGENTS.md` for the prepare/ingest workflow guidance. See
[docs/harness/kiro-codex.md](docs/harness/kiro-codex.md) for the full walkthrough
(Visual QA setup, custom Codex prompt, per-harness entry-point table).

> For the full list of environment variables and detailed client / plugin configurations, see [docs/harness/environment.md](docs/harness/environment.md).

## 2. Usage

You interact in natural language; the client drives the prepare→generate→ingest handshake
behind the scenes (guided by the bundled skills). You don't call the `prepare_*`/`ingest_*`
tools by hand — just describe what you want.

### Step 1 — Generate or Import PPT

**Create new** — Prepare your content in a file like `context.md`, then request via your MCP client:

```
Read @context.md and generate a PPT using ppt-generator.
```

The client generates the outline JSON, then the per-slide design specs, following the
prompts and schemas the server hands back — no model credentials on the server side.

**Import existing PPTX** — You can also import an existing PPTX file for editing:

```
Import @presentation.pptx using import_pptx.
```

Importing automatically generates an HTML preview. You can skip Step 2 and directly use per-slide editing, Visual QA, and export features. Parsing is deterministic with no LLM calls.

### Step 2 — Provide Project Information

Before outline generation, you will be asked for the following:

- **Presentation purpose** — e.g., "internal tech sharing", "client proposal", "conference talk"
- **Presentation duration** — 3–60 minutes (default: 15 minutes)
- **Audience type** — `general` / `technical` / `executive`
- **Presenter info** — name / title / organization

The flow proceeds Outline → DESIGN.md (design intent) → per-slide Design Spec. You review
and confirm the outline before slides are generated, and can edit at each stage.

### Step 3 — Edit Individual Slides (Optional)

After design spec generation (or PPTX import), you can modify individual slides. Instead of regenerating everything, you can add, update, delete, move, or make narrow single-component edits:

```
Add a bar chart comparing performance data below the diagram on slide 3.
Slide 5 has too much text — reduce it to key bullet points with icon layout.
Add a Q&A slide after slide 7.
Make the "LLM" box on slide 4 red.
Move slide 6 to position 2.
```

Add/update/component edits use the prepare/ingest handshake; move and delete are pure file
operations with no generation.

### Step 4 — Visual QA (Optional)

Detects and fixes visual defects (line breaks, overlaps, margin misalignment, etc.). The
server captures screenshots (Playwright); the client analyzes them and generates fixes via
the prepare/ingest handshake. **Does not run automatically — must be explicitly requested.**

**Prerequisites:**

```bash
uv sync --group visual-qa
uv run --group visual-qa playwright install chromium
```

```
Run visual QA.
```

> Visual QA is an opt-in tool. A suggestion message appears after design spec generation, but it will not run until explicitly requested. If Playwright is not installed, it can be skipped without affecting existing functionality.

### Step 5 — Export Files

After the design spec is finalized, request an HTML preview:

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

When registering the MCP server directly, add `PPT_LOG_DIR` to the `env` section:

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

> When installed as a Claude Code plugin, set `PPT_LOG_DIR` in your Claude Code MCP
> environment for the `ppt-generator` server. See [docs/harness/environment.md](docs/harness/environment.md).

### Environment Variables

| Variable | Description |
| --- | --- |
| `VISUAL_QA_PARALLEL` | Number of parallel screenshot-capture workers for Visual QA (Playwright, server-side; default: 8). Analysis/fix generation runs on the client |
| `VISUAL_QA_MAX_ITERATIONS` | Maximum fix iterations for Visual QA (default: 2) |
| `SCREENSHOT_TIMEOUT` | Per-slide screenshot capture timeout in seconds (default: 60) |
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

- [Architecture](docs/harness/architecture.md) — prepare/ingest handshake, MCP tool list, workflows, project structure
- [Environment & Config](docs/harness/environment.md) — environment variables, MCP client / plugin config
- [Kiro / Codex Setup](docs/harness/kiro-codex.md) — use the workflow as a skill in Kiro and Codex
- [Schemas](docs/harness/schemas.md) — domain models, client output models, component_hint table
- [Testing](docs/harness/testing.md) — test writing rules and patterns
- [ADR](docs/adr/) — Architecture Decision Records (the client-LLM offload decision lives under the `offload/` category)
- [Contributing Guide](CONTRIBUTING.md)
