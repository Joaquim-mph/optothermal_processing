# DVC Guide

How to access the lab DVC server, push/pull data, and configure your environment.

## Remote Server

The project is configured with a single SSH remote named `origin`:

- **URL:** `ssh://calisto@calisto-berry.local/srv/dvc-store/optothermal`
- **Auth:** SSH key (`~/.ssh/id_ed25519`)

Configuration lives in `.dvc/config` (committed) and per-machine overrides in `.dvc/config.local` (gitignored).

## One-Time Setup

### 1. Install DVC with the SSH backend

DVC's SSH support is an optional extra and must be installed explicitly:

```bash
pip install "dvc[ssh]"
```

If `pip` is missing inside your venv, bootstrap it first:

```bash
python -m ensurepip --upgrade
```

Verify:

```bash
python -c "import dvc_ssh; print('ok')"
```

### 2. Authorize your SSH key on the server

Copy your public key to the DVC server (one-time):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub calisto@calisto-berry.local
```

Test passwordless access:

```bash
ssh -i ~/.ssh/id_ed25519 calisto@calisto-berry.local 'echo ok'
```

### 3. Point DVC at your local key (only if needed)

The committed `.dvc/config` may have a Linux-style `keyfile` path that doesn't exist on macOS. Override it locally:

```bash
dvc remote modify --local origin keyfile ~/.ssh/id_ed25519
```

`--local` writes to `.dvc/config.local`, which is gitignored, so it won't break the shared config for other users.

## Daily Workflow

### Pull data (sync from server -> local)

```bash
dvc pull
```

Pulls everything tracked by `.dvc` files in the repo. To pull a specific target:

```bash
dvc pull data.dvc
```

### Push data (sync local -> server)

```bash
# 1. Update tracking after data changes
dvc add data

# 2. Commit the updated .dvc metadata to git
git add data.dvc .gitignore
git commit -m "update data"

# 3. Upload the data blobs to the remote
dvc push
```

### Check status

```bash
dvc status              # local vs. workspace
dvc status -c           # local vs. remote (cloud)
```

## Enable Auto-Stage

`core.autostage = true` makes DVC automatically `git add` the `.dvc` metafiles and `.gitignore` entries it creates, so you only need to commit:

```bash
# Just for this machine (recommended unless the team agrees on it)
dvc config --local core.autostage true

# Or repo-wide (committed to git)
dvc config core.autostage true
```

After enabling, the workflow becomes:

```bash
dvc add data            # data.dvc and .gitignore are auto-staged
git commit -m "update data"
dvc push
```

It does **not** commit and does **not** push — those steps are still manual.

## Using a Different Virtualenv

The project's `biotite` command is tied to `.venv/`, but `dvc` itself is just a Python package. You can run it from any environment that has `dvc[ssh]` installed.

### Option A: Use a separate venv for DVC

```bash
# Create a dedicated DVC venv anywhere on disk
python3 -m venv ~/.venvs/dvc
source ~/.venvs/dvc/bin/activate
pip install "dvc[ssh]"
```

Then, from inside the project directory, run:

```bash
dvc pull
dvc push
```

DVC discovers the repo via the `.dvc/` folder in the current directory — it doesn't care which Python environment invoked it.

### Option B: Install DVC globally with pipx

```bash
brew install pipx
pipx install "dvc[ssh]"
```

`pipx` installs DVC in its own isolated environment and exposes the `dvc` command on your `PATH`, so you can run it without activating any venv.

### Important caveats

- The **active venv must NOT shadow the project venv's dependencies** when running `biotite` commands. Switch back to `.venv/` (or use the absolute path `./.venv/bin/biotite`) for normal project work.
- DVC reads `.dvc/config` and `.dvc/config.local` from the repo, so the SSH remote config is the same regardless of which venv runs `dvc`.
- The SSH key (`~/.ssh/id_ed25519`) is per-user, not per-venv — once authorized on the server, it works from any environment.

## Pulling Only the Raw Data

The whole `data/` directory is tracked as a single DVC output (see `data.dvc`), so `dvc pull` is all-or-nothing — there is no per-subdirectory `.dvc` file to target. If you have local processed files in `data/02_stage/` or `data/03_derived/` that aren't recorded in DVC, `dvc pull` will refuse with:

```
ERROR: failed to pull data from the cloud - Can't remove the following unsaved files without confirmation. Use `--force` to force.
```

`--force` would clobber your local processed work. To refresh **only** `data/01_raw` while leaving `02_stage` and `03_derived` untouched, use `dvc get` to fetch a single subpath into a scratch location and overlay it:

```bash
# 1. Fetch only data/01_raw from the remote into /tmp
dvc get . data/01_raw -o /tmp/raw_from_dvc --force

# 2. (Optional) Diff to see what would change
diff <(cd /tmp/raw_from_dvc && find . -type f | sort) \
     <(cd data/01_raw       && find . -type f | sort)

# 3. Overlay into the project. cp -a preserves attributes and overwrites.
cp -a /tmp/raw_from_dvc/. data/01_raw/

# 4. Clean up the scratch copy
rm -rf /tmp/raw_from_dvc
```

`cp -a /src/. /dst/` merges (existing files are overwritten, extras in `/dst/` are kept). If you instead want a strict mirror that also deletes local raw files missing from the remote, use `rsync -a --delete /tmp/raw_from_dvc/ data/01_raw/`.

After this, `dvc status` will still report `data` as modified — that's expected and harmless. It just means your local `02_stage`/`03_derived` differ from the tracked snapshot. Run `dvc commit && dvc push` later when you want to publish processed results.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `No module named 'dvc_ssh'` | SSH extra missing | `pip install "dvc[ssh]"` in the venv running `dvc` |
| `No such file or directory: '/home/.../id_ed25519'` | `keyfile` path in `.dvc/config` is wrong for this machine | `dvc remote modify --local origin keyfile ~/.ssh/id_ed25519` |
| Password prompt instead of key auth | Public key not on server, or agent missing the key | `ssh-copy-id -i ~/.ssh/id_ed25519.pub calisto@calisto-berry.local`; or `ssh-add ~/.ssh/id_ed25519` |
| `dvc push` hangs | SSH host unreachable (lab network only?) | Confirm `ssh calisto@calisto-berry.local` works first |
