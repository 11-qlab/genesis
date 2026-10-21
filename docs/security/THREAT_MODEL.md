# Threat Model

## Assets
1. Host filesystem outside `AGI_FS_ROOT`.
2. Provider API keys (`os.environ[...]`).
3. Run history in `state/agi.sqlite3`.
4. Subprocess execution surface (`ShellTool`).

## Adversaries considered
- A model that returns malicious tool arguments (prompt injection via a
  provider reply).
- A user who runs `agi run "<goal>"` with a goal that the model interprets as
  permission to do something hostile.
- A retrieved document later (Phase 3+) whose content tries to override the
  system prompt.

## Controls in place
- **Filesystem sandbox** — every `fs_*` argument is resolved against
  `AGI_FS_ROOT` and rejected if it escapes. Tested for `..`, absolute paths, and
  symlink targets that leave the root.
- **Schema validation** — every tool invocation goes through
  `Tool.args_model.model_validate`. Type and bounds are enforced at the tool
  boundary, not in the model output.
- **Allowlisted shell** — argv[0] must be in the configured allowlist.
  `shell=False`. `rm`, `sh`, `bash`, `python`, `curl`, `wget` are not in the
  default allowlist and are never invoked from model output.
- **Key isolation** — the API key env var name is configurable; the value is
  only used to build the `Authorization` header. It is never echoed by
  `agi doctor`, `agi health`, or any test fixture.
- **No shell interpolation of model output** — the shell tool splits with
  `shlex.split` and executes the resulting argv directly.

## Out of scope (acknowledged)
- A hostile provider endpoint. TLS trust is delegated to `ssl` defaults; if you
  point `AGI_BASE_URL` at a hostile server, you get whatever that server
  returns. That is a deployment decision, not a code bug.
- Privilege escalation beyond the process user. The platform runs as the
  invoking user and makes no attempt to drop privileges.

## Resolved by test
- `tests/security/test_sandbox.py` — escape write/read/list, shell allowlist,
  shell metacharacter handling.
- `tests/unit/test_fs_tools.py` — escape write rejection on the tool itself.
- `tests/integration/test_openai_compat.py` — provider error paths (4xx, 5xx,
  malformed JSON, health failure).
