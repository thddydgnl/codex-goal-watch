# Codex OneTurn

Keep long-running local jobs in one logical Codex turn without repeated
“still running” Goal continuations or model polling.

[한국어](README.ko.md) · [Project vision (Korean)](docs/PROJECT_VISION.ko.md)

> Unofficial community project. Not affiliated with or endorsed by OpenAI.

## Choose the next README

Five GitHub-ready README concepts are available for review:

1. [Global Launch](docs/readme-options/README-01-GLOBAL-LAUNCH.md) — recommended for international discovery
2. [Korean Story](docs/readme-options/README-02-KOREAN-STORY.md) — Korean-first problem and creator story
3. [Engineering Trust](docs/readme-options/README-03-ENGINEERING-TRUST.md) — architecture, guarantees, and security
4. [Minimal](docs/readme-options/README-04-MINIMAL.md) — concise bilingual presentation
5. [Community](docs/readme-options/README-05-COMMUNITY.md) — contributions and early adopter validation

[Compare all five concepts →](docs/readme-options/README.md)

## How it works

```text
Codex model
  → OneTurn run tool
  → local process ─────────────────→ terminal event
       0 model calls while waiting
       0 extra Goal turns
  → analyze in the same Codex turn
  → final verification
  → OneTurn finish
  → turn ends
```

The bundled MCP `run` call remains open until the process completes, fails, is
cancelled, or reaches its deadline. A Stop hook prevents premature completion
and continues the same turn ID, with a three-block fail-open safety limit.

## Requirements

- Codex CLI 0.133.0 or newer
- macOS or Linux
- Python 3.10 or newer
- Codex hooks enabled (the default)

## Install

From a clone:

```bash
git clone https://github.com/thddydgnl/codex-goal-watch.git
cd codex-goal-watch
./install.sh
```

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/thddydgnl/codex-goal-watch/master/install.sh | bash
```

The installer removes the old `goal-watch` Skill, `wait_for.sh`, and its
`AGENTS.md` block before installing the OneTurn marketplace and plugin.

After installation, restart Codex, open `/hooks`, review and trust the two
OneTurn hooks, then start a new task so the bundled Skill and MCP tools load.

## Two activation paths

Ask: request a long job normally. The Skill asks before activating OneTurn.
Reply with `Run with OneTurn` or `OneTurn으로 실행` to approve it.

Direct: include OneTurn in the initial request:

```text
Use OneTurn to run the full build and test suite, fix failures, and verify the result.
```

Or explicitly invoke the Skill:

```text
$one-turn run all three training variants and compare the results.
```

There is no Auto mode. OneTurn activates only after Ask approval or explicit
wording.

## Security

- Commands run as argv arrays, never shell strings.
- Codex prompts for approval on the MCP execution tool.
- Artifact checks cannot escape the requested working directory.
- The plugin does not access ChatGPT credentials or API keys.
- The plugin makes no network requests of its own.
- Cancelling the tool terminates the child process group.
- Hook errors and repeated completion blocks fail open.

## Limits

The same-turn guarantee applies while the Codex process and session stay alive.
Restart recovery and Windows support are not part of v0.1. Multiple model calls
may still occur for analysis and fixes; the guarantee is zero model polling
while a managed process is running.

When the user does not specify a duration, each OneTurn `run` uses a default
deadline of **7 days (604,800 seconds)**. A shorter explicit deadline takes
precedence.

## Uninstall

```bash
./install.sh --uninstall
```

## Development

```bash
python3 -m unittest discover -s tests -v
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/codex-one-turn
```

## License

MIT
