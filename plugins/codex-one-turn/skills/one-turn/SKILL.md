---
name: one-turn
description: Use for a user-approved long-running local build, test, training, deploy, or batch job that should wait without repeated Codex polling turns. Ask before activation unless the user explicitly says OneTurn or invokes $one-turn.
---

# OneTurn

OneTurn has exactly two activation paths.

## 1. Direct activation

The user explicitly writes `OneTurn`, `one-turn`, `원턴`, or invokes
`$one-turn`. Proceed without asking again. The UserPromptSubmit hook injects an
`activation_id`; use that exact id for every bundled OneTurn tool call.

## 2. Ask activation

If the user did not explicitly activate OneTurn and the next required local
command will likely take longer than 60 seconds, ask once before starting it:

> 이 작업은 오래 걸릴 수 있습니다. OneTurn으로 실행할까요? 사용하려면
> `OneTurn으로 실행`이라고 답해주세요.

Do not start the long command before the answer. A normal affirmative such as
"yes" is insufficient for activation; ask the user to include `OneTurn` so the
activation hook can create a scoped state token.

There is no Auto mode. Never activate OneTurn without direct wording or the
Ask confirmation above.

## Running work

When activation context contains an `activation_id`:

1. Use the bundled OneTurn `run` MCP tool for each long local command.
2. Pass command arguments as an argv array, never as a shell command string.
3. Pass an absolute working directory.
4. Set a realistic deadline and list any required result artifacts.
5. Do not launch the same command with `nohup`, `&`, or a detached shell.
6. Do not poll status with shell calls while `run` is active. The tool returns
   only on success, failure, cancellation, or deadline.
7. After it returns, inspect the structured result, diagnose failures, and
   continue the requested work in the current turn.

The tool returning successfully means only that the process and artifact checks
passed. It does not mean the user's entire request is complete.

## Finishing

Call the bundled OneTurn `finish` MCP tool with the same `activation_id` only
after all requested work and final verification are complete. Then provide the
final response.

If you try to end early, the Stop hook continues the same Codex turn and asks
you to either keep working or call `finish`. It releases after three blocks as
a safety limit, so never rely on the hook instead of tracking the objective.

If the user cancels, do not call `finish` as if the objective succeeded. Report
the cancellation or failure accurately.
