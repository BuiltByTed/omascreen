# Omarchy package submission

These are proposed recipes for `omacom/omarchy-pkgs`. They are not published in
Omarchy's package repository yet. AUR publication is optional, not a prerequisite.

The recipes package the released Omascreen source and three dependencies that
are not currently provided by the configured Arch/Omarchy repositories:

| Package | Source | Notes |
| --- | --- | --- |
| `python-rendercanvas` | PyPI source archive | Builds a pure Python wheel. |
| `python-glfw` | PyPI source archive | Uses Arch's system `glfw` library. |
| `python-wgpu` | Upstream PyPI wheels | Includes upstream's matching native library; architecture-specific artifacts have checksums. |
| `omascreen` | GitHub release source | Installs system-wide, including menu entry, icon, docs, and tests. |

Each recipe has `.omarchy/package.json` metadata tracking the corresponding PyPI
or GitHub release. None requests the fast release ring: Python modules must move
through Omarchy's normal release channels.

## Build and verify

Use Omarchy's own repository and container builder:

```sh
git clone https://github.com/omacom/omarchy-pkgs.git
cp -a packaging/omarchy/pkgbuilds/. omarchy-pkgs/pkgbuilds/
cd omarchy-pkgs
bin/build --package python-rendercanvas python-glfw python-wgpu omascreen
```

The build requires a working Docker or Podman installation. It builds each recipe
in an isolated container and stages dependencies for later packages. Output is
under `build-output/edge/x86_64/`. A plan-only check uses `--dry-run`; that is not
a successful build. Omascreen's [Arch packages workflow](../../.github/workflows/arch-package.yml)
runs this same builder on GitHub, installs the packages into a fresh container,
checks the command, launcher, VNC dependency and GUI shutdown, and uploads the
resulting packages.

Check release discovery with:

```sh
python helpers/upstream-watch.py check pkgbuilds/omascreen
```

Test aarch64 with the builder's `--arch aarch64` option or native Omarchy CI.
The local/hosted x86_64 build does not establish aarch64 runtime compatibility.

## Submit

Follow the current [contribution guide](https://github.com/omacom/omarchy-pkgs#contribute-a-package):

1. Fork `omacom/omarchy-pkgs` and branch from its `master`.
2. Submit one package per PR. The dependency recipes need to land before the
   Omascreen recipe can build against the published Omarchy repository.
3. Include the package purpose, source/binary details, and actual build/test results.
4. A maintainer must approve builds for a new contributor. After the required
   checks and merge, packages publish to `edge`; promotion brings them to `rc`
   and `stable`. Acceptance and timing belong to the Omarchy maintainers.

Once Omascreen is available in a user's channel, installation becomes:

```sh
omarchy pkg add omascreen
```

## Switching from the per-user installer

The package installs `/usr/bin/omascreen` and a system desktop entry. Existing
`~/.local/bin/omascreen` and the per-user desktop entry can shadow those. After
installing the system package, remove the two old command symlinks and the
per-user manager entry, retaining the venv until all connection launchers have
been refreshed. Recreate each launcher with `/usr/bin/omascreen shortcut NAME`,
or open `/usr/bin/omascreen` and toggle its app-menu checkbox off and on.
Profiles, cached artwork, and keyring passwords use the same locations in both
installation methods.
