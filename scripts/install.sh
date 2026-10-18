#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/omascreen"
bin_dir="$HOME/.local/bin"
mkdir -p "$install_dir" "$bin_dir"
if command -v uv >/dev/null; then
  if [[ ! -x "$install_dir/venv/bin/python" ]]; then
    uv venv "$install_dir/venv"
  fi
  uv pip install --python "$install_dir/venv/bin/python" "$source_dir"
else
  if [[ ! -x "$install_dir/venv/bin/python" ]]; then
    python3 -m venv "$install_dir/venv"
  fi
  "$install_dir/venv/bin/python" -m pip install "$source_dir"
fi
ln -sfn "$install_dir/venv/bin/omascreen" "$bin_dir/omascreen"
ln -sfn "$install_dir/venv/bin/screen-sharing" "$bin_dir/screen-sharing"
"$install_dir/venv/bin/python" - <<'PY'
from screen_sharing.native.profiles import ProfileStore
from screen_sharing.native.shortcuts import create_manager, create, shortcut_path
create_manager()
for profile in ProfileStore().load():
    if shortcut_path(profile).exists():
        create(profile)
PY
printf 'Installed Omascreen. Open it from the app menu or run: omascreen\n'
