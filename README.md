# agentic-go-contributor

A CLI tool that takes a GitHub issue from any Go open-source project, explores the repository with a tool-using AI agent, makes a minimal code change, validates it with `go build` + `go test`, and produces a PR-ready patch and summary.

```bash
python agent.py --issue https://github.com/spf13/cobra/issues/1272
```

Outputs land in `output/cobra-1272/`:
- `changes.patch` — `git diff` of the agent's edits, ready to apply
- `pr_summary.md` — PR title + body with a Self-Review section
- `run.log` — full trace of the agent's reasoning and tool calls

## Why this exists

Most "AI fixes GitHub issues" demos are thin wrappers: one prompt, one shot, no validation. This project is a small but deliberate **framework** around the LLM:

- A required workflow (PLAN → EDIT → diff-review → VALIDATE → REFLECT → SELF-REVIEW)
- Concrete, well-scoped tools (`grep`, `read_file`, `edit_file`, `git_diff`, `run_build`, `run_tests`, `finish`)
- Failure handling that forces the agent to *reason* about errors before retrying
- A Self-Review step that surfaces confidence and residual risk in the PR body

The point is reliability on small/medium issues, not autonomy on hard ones.

## Setup

### Requirements
- Python 3.10+
- Go (any recent version) — the agent shells out to `go build` and `go test`
- A free Gemini API key (https://aistudio.google.com/apikey)
- A GitHub personal access token with `public_repo` scope (https://github.com/settings/tokens)

### Install
```bash
git clone https://github.com/nilesh07g/agentic-go-contributor
cd agentic-go-contributor
pip install -r requirements.txt
```

### Configure
```bash
cp .env.example .env
# edit .env and paste your two keys
```

### Verify
```bash
python scripts/check_keys.py
```

Expected:
```
[OK]   Gemini API: got reply 'hello'
[OK]   GitHub API: fetched issue '...'
[OK] All keys working. Ready to run agent.py.
```

## Usage

```bash
python agent.py --issue <github_issue_url>
```

Works with any public GitHub issue on a Go repo. Examples:

```bash
python agent.py --issue https://github.com/spf13/cobra/issues/1272
python agent.py --issue https://github.com/gin-gonic/gin/issues/3000
```

The agent will:
1. Fetch the issue text + comments via GitHub API
2. Clone the target repo into `./workspaces/<repo>/` (reused on subsequent runs)
3. Run the agent loop (capped at 15 iterations, with rate-limit pauses)
4. Validate the result with `go build ./...` and `go test ./...`
5. Drop the patch + summary into `./output/<repo>-<N>/`

To apply the resulting patch to a fresh clone:
```bash
git clone <repo>
cd <repo>
git apply /path/to/changes.patch
```

## How it works

```
┌──────────────────────────────────────────────┐
│  CLI: python agent.py --issue <url>          │
└──────────────────────────────────────────────┘
            │
            ▼
   ┌────────────────────┐
   │ Fetch issue        │
   │ Clone target repo  │
   │ Create branch      │
   └────────┬───────────┘
            ▼
   ┌────────────────────┐
   │   Agent loop       │  Gemini + native function calling
   │   (max 15 turns)   │
   └────────┬───────────┘
            │
   Tools the agent can call:
   ├─ list_dir
   ├─ read_file (paginated)
   ├─ grep (Python regex over text files)
   ├─ edit_file (exact replace, fails on ambiguity, warns on large edits)
   ├─ git_diff (self-review of pending changes)
   ├─ run_build (go build ./...)
   ├─ run_tests (go test, package-scoped or full)
   └─ finish (commits the PR title + body, ends the loop)
            │
            ▼
   ┌────────────────────┐
   │  Write artifacts:  │
   │  changes.patch     │
   │  pr_summary.md     │
   │  run.log           │
   └────────────────────┘
```

## Required workflow (enforced by the system prompt)

The agent must follow this order on every issue:

1. **UNDERSTAND** — read the issue text carefully
2. **EXPLORE** — `list_dir`, `grep`, `read_file` to locate relevant code
3. **PLAN** — a structured block with relevant files, hypothesis, scope check, planned changes, validation strategy
4. **EDIT** — minimal, surgical `edit_file` calls
5. **REVIEW THE DIFF** — call `git_diff()` and check that only intended files were touched
6. **VALIDATE** — `run_build`, then `run_tests`
7. **REFLECT on failure** — if validation fails, write a structured REFLECTION block before retrying (max 3 cycles)
8. **SELF-REVIEW** — answer in natural language: how does this solve the issue, what risks remain, confidence high/medium/low
9. **FINISH** — call `finish(pr_title, pr_body)` — the body must contain the Self-Review answers

The PLAN block includes a **Scope check** rule: state the root cause in general terms, then check whether the same root cause appears in other places in the file/codebase. This catches bugs that span multiple sites.

## Design choices

- **Single agent, not multi-agent.** A planner/coder/reviewer split adds failure modes and complexity without enough payoff for small/medium issues.
- **No RAG / embeddings.** For codebases up to ~50k LOC, `grep` + `read_file` give the agent everything it needs and are cheaper to debug than a vector index.
- **`git_diff()` as a self-review tool.** After every edit the agent inspects its own diff before validating. Catches "wrong file edited" / "diff too large" early.
- **Edit-safety guardrails.** `edit_file` requires `old_str` to be unique (hard fail) and warns on large or expansive edits (soft warning surfaced in the log). Prevents accidental sprawl without brittle hard blocks.
- **Mandatory Self-Review before `finish`.** The agent must reason about issue alignment, not just "tests pass". The Self-Review section in `pr_summary.md` makes the agent's confidence inspectable.
- **Tool-based, not free-form.** The agent can only affect the world through the tools defined in `tools/`. This is what makes the system a framework rather than a prompt wrapper.
- **LLM-agnostic core.** `llm.py` is the only Gemini-specific file. Swapping to Claude or OpenAI is a one-file change.
- **Free-tier friendly.** Defaults to `gemini-2.5-flash` with a built-in retry on 429 rate limits. Whole project runs at $0.

## Project layout

```
.
├── agent.py             # CLI entry, agent loop, output writer
├── llm.py               # Gemini client wrapper with 429 retry
├── github_client.py     # fetch issue + comments
├── workspace.py         # clone / reset target repo, make patch
├── tools/
│   ├── fs.py            # list_dir, read_file, edit_file (with size warnings)
│   ├── search.py        # grep
│   ├── git.py           # git_diff (self-review)
│   ├── runner.py        # run_build, run_tests
│   └── schemas.py       # Gemini function declarations
├── prompts/
│   └── system.md        # the agent's system prompt
├── scripts/
│   └── check_keys.py    # smoke test for both API keys
├── verify/              # standalone Go programs to verify fixes by behavior
├── sample_runs/         # worked examples
├── output/              # generated artifacts (gitignored)
├── workspaces/          # cloned target repos (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## Limitations

- **Multi-site root causes.** When the same bug pattern lives in multiple functions (e.g., `AddCommand` and `RemoveCommand`), small free-tier models often fix one site and miss the rest. The `verify/` programs are a manual safety net for this; an automated behavioral-verify tool is the next planned addition.
- **Existing tests don't always cover the bug.** A passing test suite is *necessary but not sufficient* — the agent's `pr_summary.md` includes a Self-Review section to make this gap visible.
- **Free-tier rate limits.** `gemini-2.5-flash` allows about 5 requests/minute on the free tier, so a typical run takes 2–4 minutes. The loop sleeps between calls and retries on 429.
- **Single language target.** Tools and validation are Go-specific (`go build`, `go test`). Extending to other languages means adding language-specific runner tools.

## Extending

- **Different LLM** — swap providers by editing `llm.py`; the system prompt is provider-agnostic.
- **More languages** — add a `runner_<lang>.py` for `cargo`/`pytest`/`npm test`, register it in `tools/schemas.py`, and adjust the system prompt's validation step.
- **Embeddings / RAG** — ingest the repo at workspace setup, expose a `semantic_search` tool, register it in `tools/schemas.py`. Useful for very large repos where `grep` is too noisy.
- **Behavioral verification** — add `write_demo` + `run_demo` tools so the agent can write and execute a small program that reproduces the bug, before and after editing.

## Sample runs

See `sample_runs/` for worked examples on real issues.

## License

MIT (the agent code itself; cloned target repos retain their own licenses).
