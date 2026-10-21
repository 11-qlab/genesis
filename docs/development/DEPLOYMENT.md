# Deployment

The platform is designed to run in place as a research tool. There is no
container image, no published wheel, and no remote service to configure. This
document describes the two supported deployment shapes.

## Shape 1 — workstation / chroot (default)

Use from the repository checkout:

    cd /path/to/AGI
    bash scripts/setup.sh          # verifies python + deps, runs tests
    bash scripts/install.sh        # optional: link bin/agi into ~/.local/bin
    bin/agi doctor
    bin/agi run "list the workspace"

Requirements:

- Python >= 3.11 with `pydantic`, `typer`, `rich`, `pytest`, `ruff`.
- No network access needed for `echo` provider. Network is needed only for
  `openai_compat` and only if `AGI_BASE_URL` is remote.
- Disk: the state file lives in `state/agi.sqlite3`; checkpoints (none yet)
  would live under `checkpoints/`.

`scripts/install.sh` is idempotent and refuses to overwrite a foreign symlink.
It only writes to `~/.local/bin/agi`.

## Shape 2 — background service (optional)

`agi serve` binds loopback only by default. To run it under systemd:

    # ~/.config/systemd/user/agi.service
    [Unit]
    Description=AGI research platform HTTP API (loopback)
    After=network.target

    [Service]
    Type=simple
    WorkingDirectory=/path/to/AGI
    Environment=PYTHONPATH=/path/to/AGI/src
    Environment=AGI_STORAGE_PATH=/path/to/AGI/state/agi.sqlite3
    Environment=AGI_FS_ROOT=/path/to/AGI/state/workspace
    ExecStart=/usr/bin/python3 -m agi serve --port 8000
    Restart=on-failure

    [Install]
    WantedBy=default.target

Enable and start:

    systemctl --user daemon-reload
    systemctl --user enable --now agi.service
    curl http://127.0.0.1:8000/health

### Binding beyond loopback

The CLI refuses non-loopback hosts without `--allow-remote`. If you have a
compelling reason to bind an external interface, you also need to add an
authentication layer that does not exist today. Do not run `--allow-remote`
against an untrusted network. The sandbox is robust against the CLI, not
against a stranger on the wire.

## Backup

The only persistent state is `state/agi.sqlite3`. Copy it while the process is
stopped, or use `sqlite3 state/agi.sqlite3 ".backup state/agi.backup.sqlite3"`
from another shell (safe under WAL). `state/workspace/`, `checkpoints/`, and
`artifacts/` are user content; back them up with the tool of your choice.

## Recovery

If the SQLite file is corrupted:

    sqlite3 state/agi.sqlite3 "PRAGMA integrity_check;"

If it reports anything other than `ok`, restore from the most recent `.backup`
file. There is no migration machinery today; the schema is additive.

## Reproducible install (not yet automated)

A lockfile-based install would go:

    pip-compile --generate-hashes pyproject.toml > requirements.lock
    pip install --require-hashes -r requirements.lock

The command is documented here but not automated because the current
environment forbids network installs. When a build machine is available, add
`requirements.lock` to the repo and a `make lock` target. Do not commit the
lockfile without having generated it from the actual `pyproject.toml` in the
same commit.
