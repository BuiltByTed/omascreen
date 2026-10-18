#!/usr/bin/env bash
set -euo pipefail

# The builder image includes Omarchy's keyring, but adds its repository only
# when running a build. Recreate that repository for this fresh-install check.
sudo pacman-key --init
sudo sed -i '/^\[core\]$/i [omarchy]\nSigLevel = Required DatabaseOptional\nServer = https://pkgs.omarchy.org/edge/x86_64\n' /etc/pacman.conf
sudo pacman -Syu --noconfirm
sudo pacman -U --noconfirm /packages/*.pkg.tar.zst
QT_QPA_PLATFORM=offscreen python /checks/smoke-installed.py
