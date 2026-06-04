# agentic-go-contributor

A CLI that takes a GitHub issue from any Go open-source project, explores the repository with a tool-using AI agent, makes a minimal code change, validates it with `go build` + `go test` + a behavioral demo it writes for itself, and produces a PR-ready patch and summary.

```bash
python agent.py --issue https://github.com/spf13/cobra/issues/1272
```

Outputs land in `output/<repo>-<issue#>/`:
- `changes.patch` — `git diff` of the agent's edits (apply with `git apply`)
- `pr_summary.md` — PR title + body with a Self-Review section (confidence, residual risk)
- `run.log` — full trace of the agent's reasoning, every tool call, and every reflection

## Table of contents

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [Required workflow](#required-workflow-enforced-by-the-system-prompt)
- [Quick start (clone → run in 5 minutes)](#quick-start)
- [Sample runs](#sample-runs)
- [Findings from running the agent](#findings-from-running-the-agent)
- [Limitations](#limitations)
- [Future work](#future-work)
- [Project layout](#project-layout)
- [Extending](#extending)

---

## Why this exists

Most "AI fixes GitHub issues" demos are thin wrappers: one prompt, one shot, no validation. This project is a small but deliberate **framework** around the LLM:

- A required workflow: **PLAN** → **EDIT** → **DIFF-REVIEW** → **VALIDATE** → **BEHAVIORAL VERIFY** → **REFLECT** → **SELF-REVIEW** → **FINISH**.
- 10 concrete, well-scoped tools that operate on the cloned target repo
- Failure handling that forces the agent to *reason* about errors before retrying (max 3 reflection cycles)
- Behavioral verification: the agent writes and runs a small Go program to confirm its fix changes observable behavior, not just that tests pass
- A Self-Review step that surfaces confidence and residual risk in the PR body

The goal is reliability on small/medium issues, not autonomy on hard ones — and **visible** reasoning at every step so a reviewer can see exactly what the agent did and why.

---

## How it works

```
┌──────────────────────────────────────────────┐
│  CLI: python agent.py --issue <url>          │
└──────────────────────────────────────────────┘
            │
            ▼
   ┌────────────────────────────┐
   │  github_client: fetch      │
   │  issue title/body/comments │
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │  workspace: clone + reset  │
   │  target repo to clean main │
   │  on a fresh issue branch   │
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │  Agent loop (Gemini +      │
   │  native function calling)  │
   │  max 15 iterations,        │
   │  rate-limit-aware retries  │
   └────────────┬───────────────┘
                │
   Tools the agent can call:
   ├─ list_dir(path)
   ├─ read_file(path, line_start?, line_end?)        — paginated, line-numbered
   ├─ grep(pattern, path?)                            — Python regex over text files
   ├─ edit_file(path, old_str, new_str)               — exact replace, unique-match required, warns on large edits
   ├─ git_diff()                                      — agent self-reviews its own pending changes
   ├─ write_demo(name, content)                       — writes a standalone Go program in a sibling dir
   ├─ run_demo(name)                                  — builds and runs the demo; returns stdout+stderr
   ├─ run_build()                                     — go build ./...
   ├─ run_tests(package?)                             — go test, package-scoped or full
   └─ finish(pr_title, pr_body)                       — commits the summary and ends the loop
                │
                ▼
   ┌────────────────────────────┐
   │  Output writer:            │
   │  output/<repo>-<N>/        │
   │    changes.patch           │
   │    pr_summary.md           │
   │    run.log                 │
   └────────────────────────────┘
```

---

## Required workflow (enforced by the system prompt)

The agent must follow this sequence on every issue. Skipping a step is a prompt violation that the next user message will call out.

1. **UNDERSTAND** — re-read the issue text + comments
2. **EXPLORE** — `list_dir`, `grep`, `read_file` to locate relevant code (with 2-3 lines of surrounding context)
3. **PLAN** — a structured block listing:
   - Relevant files
   - Hypothesis (root cause in general terms)
   - Scope check (does the same root cause appear elsewhere?)
   - Planned changes
   - Validation strategy
4. **EDIT** — minimal, surgical `edit_file` calls
5. **REVIEW THE DIFF** — call `git_diff()` and check that only intended files were touched
6. **VALIDATE** — `run_build`, then `run_tests`
6b. **BEHAVIORAL VERIFY** — for any user-observable bug, `write_demo` + `run_demo` to confirm the fix changes observable behavior. May be skipped only for purely internal changes (refactors, comment typos)
7. **REFLECT on failure** — if validation fails, write a structured REFLECTION block (what failed / root cause guess / next action) before retrying. Max 3 reflection cycles
8. **SELF-REVIEW** — answer in natural language: how does this solve the issue, what did the demo show, what risks remain, confidence high/medium/low
9. **FINISH** — call `finish(pr_title, pr_body)` — the body must include the Self-Review answers

The PLAN block's **Scope check** rule asks the agent to state the root cause in *general* terms (not just the cited site), then check whether the same root cause appears elsewhere. This catches bugs that span multiple sites.

---

## Quick start

### Requirements

- **Python 3.10+**
- **Go 1.20+** — the agent shells out to `go build` and `go test`; install from https://go.dev/dl/
- A **free Gemini API key** — https://aistudio.google.com/apikey (no credit card required)
- A **GitHub personal access token** with `public_repo` scope — https://github.com/settings/tokens

### Setup (5 minutes)

```bash
# 1. Clone
git clone https://github.com/nilesh07g/agentic-go-contributor
cd agentic-go-contributor

# 2. Python dependencies
pip install -r requirements.txt

# 3. Verify Go is installed and on PATH
go version
# expected: go version go1.x.x ...

# 4. Configure API keys
cp .env.example .env
# edit .env and paste your two keys
```

`.env` should look like:
```
GEMINI_API_KEY=AQ.Ab...your_actual_gemini_key
GITHUB_TOKEN=ghp_...your_actual_github_token
```

### Verify keys work

```bash
python scripts/check_keys.py
```

Expected output:
```
[OK]   Gemini API: got reply 'hello'
[OK]   GitHub API: fetched issue '...'
[OK] All keys working. Ready to run agent.py.
```

### Run on an issue

```bash
python agent.py --issue https://github.com/spf13/cobra/issues/1272
```

This will:
1. Fetch the issue via GitHub API
2. Clone `spf13/cobra` into `./workspaces/cobra/` (reused on subsequent runs — reset to clean main each time)
3. Run the agent loop (max 15 iterations, ~6 second sleep between LLM calls to respect free-tier rate limits, auto-retry on 429s)
4. Validate with `go build ./...` and `go test`
5. Write artifacts to `./output/cobra-1272/`

Expect a run to take **2–5 minutes** on the free tier.

### Apply the resulting patch

```bash
# Apply to a fresh cobra clone:
git clone https://github.com/spf13/cobra /tmp/cobra-test
cd /tmp/cobra-test
git apply /path/to/agentic-go-contributor/output/cobra-1272/changes.patch
git diff   # see the change
go test ./...   # verify nothing broke
```

---

## Sample runs

Pre-recorded sample runs are checked in under `sample_runs/`. They include the agent's full output for inspection without needing to run it yourself.

### [`sample_runs/cobra-1272/`](sample_runs/cobra-1272/)
**Issue:** [Hidden Commands Should be Ignored When Calculating Use Indentation](https://github.com/spf13/cobra/issues/1272)

Contents:
- `changes.patch` — the agent's diff (+13 −11 lines in `command.go`)
- `pr_summary.md` — PR title, Problem, Fix, Test Plan, Self-Review
- `agent_demo.go` — the Go program the agent wrote and ran to verify behavior
- `run.log` — full agent trace, every PLAN, tool call, and self-review
- `NOTES.md` — honest discussion of what the framework caught and where it fell short

This sample showcases both strengths (right file, all 3 length checks guarded, clean self-review) and an honest limitation (the bug also lives in a sibling function `RemoveCommand` that the agent did not extend the fix to). See the NOTES.md for the detailed walkthrough.

---

## Findings from running the agent

These are observations from running the agent on real cobra issues. They're not weaknesses of the LLM specifically — they're general patterns worth knowing about any autonomous coding agent.

### Where the framework works well

- ✅ **Locating the right files.** The grep + paginated read combination is fast and effective. The agent reliably finds the right function on the first or second try.
- ✅ **Producing plausible, minimal diffs.** `edit_file`'s exact-replace + uniqueness guard prevents the model from making sprawling changes.
- ✅ **Running validation.** Every run completes the build + test cycle. Reflection on test failures works as designed.
- ✅ **Producing a structured PR summary.** The Self-Review section gives the reviewer a confidence rating, a why-this-works narrative, and a residual risk statement.
- ✅ **Visibility.** Every run produces a `run.log` showing every PLAN, every tool call with arguments, every REFLECTION on failure, and the final Self-Review. A reviewer can audit exactly what happened.

### Where the framework hits its limits (and why)

1. **Multi-site root causes** — when a bug pattern lives in multiple functions, free-tier models tend to fix one site and stop. Our sample run on cobra #1272 demonstrates this: the agent correctly fixes `AddCommand` but misses the parallel bug in `RemoveCommand`. Cobra's own tests pass either way (no regression test for the symptom), so there's no automatic signal that the fix is incomplete.

2. **Issue text anchoring** — issues that name one function tend to anchor the agent on that function. Reporters describe the symptom they noticed, not necessarily the full root-cause scope. The agent (reasonably) trusts the issue. A more robust system would force the agent to trace data flow from the symptom variable to all of its write sites.

3. **Behavioral demo design** — the new `write_demo` + `run_demo` tools work mechanically, but designing a demo that exercises *the actual reported symptom* (rather than a similar-sounding behavior) is itself a reasoning task. Smaller free-tier models sometimes write demos that look right but test the wrong thing. For #1272, the agent's demo verified "hidden command doesn't appear in the list" — true but not the bug, which was about column width pollution.

4. **Tests passing ≠ issue solved** — the deepest issue. Most OSS test suites cover the happy path; they don't have regression tests for every reported bug. When `go test ./...` returns OK, the agent's reward signal flips green even if the user-visible symptom is still there. This is the central reliability challenge for autonomous coding agents — not specific to this framework.

---

## Limitations

- **Single language.** Validation tools are Go-specific (`go build`, `go test`). Other languages need their own runner tool.
- **Single repo per run.** The agent operates inside the cloned target repo only; no cross-repo refactoring.
- **No model fallback.** If Gemini misunderstands the issue, the agent will likely fail rather than escalate. There is no second model to second-guess it.
- **Free-tier rate limits.** Gemini's free tier allows ~5–20 requests/minute and a daily quota. The framework sleeps between calls and retries on 429s, but you can exhaust the daily quota with ~5–10 runs of a typical issue.
- **No issue-triage step.** Vague or under-specified issues get attempted anyway. A real triage step (ask: is this scope clear? is it small? is it well-formed?) would reject 20% of issues before wasting compute.
- **Self-grading.** Confidence in the Self-Review is the agent's own assessment. It can be wrong (and was, in the #1272 sample).

---

## Future work

In priority order — these would meaningfully improve agent reliability:

1. **Data-flow scope check.** After identifying the variable that causes the symptom, automatically `grep` every line that writes to it and require the agent to consider whether each write site also needs the fix. Catches the multi-site failure mode above.
2. **Per-issue behavioral spec.** Rather than the agent designing its own demo, accept a small expected-behavior spec alongside the issue (e.g., "this CLI invocation should produce this output"). Use it as ground truth for the behavioral verify step.
3. **Issue-triage stage.** Before the agent loop, classify the issue: scope (single-site / multi-site / architectural), clarity (well-specified / vague), and reproducibility. Skip or flag issues that don't pass triage.
4. **Multi-model ensemble.** Run the agent with two different models in parallel and surface disagreements to the reviewer. Disagreement is a strong signal that the issue is not as clear-cut as the agent thinks.
5. **Embeddings / RAG.** For repos in the 100k+ LOC range where `grep` becomes noisy. Add a `semantic_search` tool that ingests the repo once and answers natural-language queries about it.
6. **Cross-repo support.** Extend `workspace.py` to support multiple cloned repos and add a `runner_<lang>.py` per language family (Rust/Python/JS/Java).
7. **Cost telemetry.** Track tokens and dollars per run so reviewers can compare cost-quality tradeoffs across models.

---

## Project layout

```
.
├── agent.py             # CLI entry, agent loop, output writer
├── llm.py               # Gemini client wrapper with 429 retry
├── github_client.py     # fetch issue + comments
├── workspace.py         # clone / reset target repo, generate patch
├── tools/
│   ├── fs.py            # list_dir, read_file, edit_file (with size warnings)
│   ├── search.py        # grep
│   ├── git.py           # git_diff (self-review)
│   ├── demo.py          # write_demo, run_demo (behavioral verify)
│   ├── runner.py        # run_build, run_tests
│   └── schemas.py       # Gemini function declarations
├── prompts/
│   └── system.md        # the agent's system prompt with the required workflow
├── scripts/
│   └── check_keys.py    # smoke test for both API keys
├── verify/              # standalone Go programs to verify fixes by behavior (manual harness)
├── sample_runs/         # pre-recorded sample agent runs with NOTES
├── output/              # generated artifacts (gitignored)
├── workspaces/          # cloned target repos (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Extending

- **Different LLM** — `llm.py` is the only Gemini-specific file. Swapping to Claude or OpenAI is a one-file change. The system prompt is provider-agnostic.
- **Other languages** — add `tools/runner_<lang>.py` for `cargo`/`pytest`/`npm test`, register declarations in `tools/schemas.py`, and adjust the system prompt's validation step.
- **More tools** — drop a new function in `tools/`, add its declaration in `tools/schemas.py`, register it in `agent.py`'s `build_dispatch`. The agent will discover it on the next run.
- **Different repo** — pass any GitHub issue URL. `workspace.py` already handles any GitHub repo.

---

## License

MIT (the agent code itself; cloned target repos retain their own licenses).
