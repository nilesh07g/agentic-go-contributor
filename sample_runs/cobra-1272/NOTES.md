# Sample run: cobra issue #1272

**Issue:** [Hidden Commands Should be Ignored When Calculating Use Indentation](https://github.com/spf13/cobra/issues/1272)

**Model used:** `gemini-2.5-flash-lite` (free tier)

## What the agent did, autonomously

1. **PLAN** — identified `command.go` as the relevant file. Stated the hypothesis that hidden commands were being counted in length calculations.
2. **EXPLORE** — used `grep` on `c.Hidden`, then `grep` on `func (c *Command) AddCommand`, then read the surrounding lines.
3. **EDIT** — wrapped all three length checks (`commandsMaxUseLen`, `commandsMaxCommandPathLen`, `commandsMaxNameLen`) inside an `if !x.Hidden { … }` block in `AddCommand`. Diff: +13 -11 lines.
4. **REVIEW** — called `git_diff()` and confirmed the change matched its PLAN.
5. **VALIDATE** — `go build ./...` passed. `go test ./command` failed transiently (path quirk on Windows); switching to `go test ./...` passed cleanly.
6. **BEHAVIORAL VERIFY** — called `write_demo` to create `agent_demo.go`, then `run_demo` to execute it. Confirmed visible commands appear and hidden commands do not.
7. **SELF-REVIEW + FINISH** — wrote the PR summary with confidence `high`.

## What's in this directory

| File | Description |
|---|---|
| `changes.patch` | The agent's `git diff` — apply to a fresh cobra clone with `git apply` |
| `pr_summary.md` | Agent-generated PR title, body, test plan, and Self-Review |
| `agent_demo.go` | The behavioral demo the agent wrote and ran |
| `run.log` | Full agent trace — every PLAN, tool call, REFLECTION, and SELF-REVIEW block |

## Observations worth calling out

**What the framework did well:**
- The agent correctly identified the right file and right function on the first try (via `grep`).
- The fix wraps all three length variables in a single guard — more thorough than wrapping just the cited one.
- The agent wrote and ran its own behavioral demo, confirming the change had observable effects.
- The Self-Review is honest about scope ("narrowly scoped to AddCommand").

**Where there's room to improve:**
- The agent's demo asserted "hidden command does not appear in the list" — true, but that wasn't the actual symptom from the issue. The real symptom is *padding width pollution*: even though the hidden command isn't shown, its name length was inflating the column width of visible commands.
- An equivalent bug pattern exists in `Command.RemoveCommand` (a recompute loop on lines 1414-1434 of `command.go`) which `InitDefaultHelpCmd` indirectly triggers. The agent didn't extend the fix to that site.
- A more rigorous demo would set up a long-named hidden command alongside short visible ones and assert the column width hasn't been inflated. See `verify/main.go` in the repo root for an example of such a test — running it after applying this patch still shows the padding bug, because `RemoveCommand` re-pollutes the lengths.

**Takeaway:** Free-tier models reliably find the right area and apply a plausible fix, but designing a *rigorous* behavioral test is itself a reasoning task that smaller models tend to underspecify. The combination of structured workflow + verification tools + a maintained `verify/` harness for important issues is more reliable than relying on the agent alone.
