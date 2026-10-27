# ub-mode

`ub-mode` is an agent skill that enforces disciplined software engineering principles when writing or changing code. It is loosely based on portions of [@poteto](https://github.com/poteto)'s rules (`poteto-mode` / `pstack`), reduced and paired with deterministic quality-gate tools:

1. **First Make it Work** — Laziness Protocol, Foundational Thinking, TDD, Redesign From First Principles, Attack the Premise, Subtract Before You Add, Outcome-Oriented Execution, Build the Lever, and Architecture (Model the Domain, Boundary Discipline, Type System Discipline, Make Operations Idempotent, Separate Before Serializing Shared State).
2. **Then Make it Right** — Fix Root Causes, Sequence Work into Verifiable Units, Test Behavior (Not Implementation), [Crapper](https://github.com/unclebob/crapper) (`CRAP < 10`), [Dryer](https://github.com/unclebob/dryer) (duplication `< 0.8`), [Mutator](https://github.com/unclebob/mutator) (cover the uncovered, kill the survivors, delete dead code), and Refactoring.
3. **Practice** — Keep a Log, Guard the Context Window, Worktree Cleanup, and Commit and Push in small ordered commits.

## Companion Tool Repositories

`ub-mode` relies on deterministic quality-gate tools to enforce structure, complexity, duplication, and test thoroughness:

- [unclebob/crapper](https://github.com/unclebob/crapper) — Computes cyclomatic complexity, test coverage, and CRAP score per function so every function stays under the CRAP threshold (`< 10`).
- [unclebob/dryer](https://github.com/unclebob/dryer) — Detects structural code duplication so duplicate blocks (`>= 0.8` similarity) are eliminated.
- [unclebob/mutator](https://github.com/unclebob/mutator) — Runs mutation testing to expose uncovered code and surviving mutants that tests fail to catch.
- [unclebob/uml-viewer](https://github.com/unclebob/uml-viewer) — Visualizes components, coverage, CRAP, mutation scores, and dependency directions.

## Installation

Install this repository as an [Agent Plugins v1](https://agent-plugins.org/specification) package using a compatible client. The portable manifest is `plugin.json`, and the skill is at `skills/ub-mode/SKILL.md`.

For manual installation, copy the entire `skills/ub-mode/` directory into
your agent's skills directory as `ub-mode/` (for example
`~/.grok/skills/ub-mode/`, `~/.claude/skills/ub-mode/`, or
`~/.cursor/skills/ub-mode/`), then invoke `/ub-mode`. The bundled
`scripts/` directory is required for the companion tools.

## Unified tool command

The repository provides one entry point for all companion tools. Python 3 and
Git are required; the first Python tool call downloads their latest upstream
sources into a shared virtual environment outside the examined project.

From this repository, optionally preinstall them:

```bash
./skills/ub-mode/scripts/ub install
```

Then run `ub` from the root of the project you want to check. Resolve the
script from the installed skill directory, or link it into a directory already
on your `PATH`:

```bash
<skill-directory>/scripts/ub crapper --changed
<skill-directory>/scripts/ub dryer src
<skill-directory>/scripts/ub mutator --changed
<skill-directory>/scripts/ub uml
```

Arguments and the working directory pass through unchanged; `ub <tool> --help`
shows the tool's own options. Run `ub install` again to update the Python
tools. `UB_MODE_HOME` overrides their default installation directory,
`~/.local/share/ub-mode`.

`ub uml` uses uml-viewer's own installer. Its first run creates `./uml`,
`./get-uml-viewer`, and `.uml-viewer/` in the examined project, then starts
the viewer. This tool also requires zsh, Clojure CLI, and Java 21 or later.
