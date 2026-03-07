#!/usr/bin/env bash
set -euo pipefail

IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not installed. Please install uv and re-run."
  exit 1
fi

current_name="$(basename "$repo_root")"
read -r -p "Project name [$current_name]: " project_name
project_name="${project_name:-$current_name}"

if [[ "$project_name" != "$current_name" ]]; then
  parent_dir="$(dirname "$repo_root")"
  target_dir="$parent_dir/$project_name"
  if [[ -e "$target_dir" ]]; then
    echo "Target directory already exists: $target_dir"
    exit 1
  fi
  mv "$repo_root" "$target_dir"
  repo_root="$target_dir"
  cd "$repo_root"
fi

if [[ -d "$repo_root/.git" ]]; then
  rm -rf "$repo_root/.git"
fi
git init

read -r -p "Remote git URL (leave blank to skip): " remote_url

read -r -p "Python version for uv pin [3.12]: " python_version
python_version="${python_version:-3.12}"
uv python pin "$python_version"

if [[ ! -f "$repo_root/pyproject.toml" ]]; then
  uv init
fi

uv venv

read -r -p "Initialize template dependencies with make init? [Y/n]: " install_deps
install_deps="${install_deps:-Y}"
if [[ "$install_deps" =~ ^[Yy]$ ]]; then
  make init
fi

if [[ -f "$repo_root/.env.example" && ! -f "$repo_root/.env" ]]; then
  cp "$repo_root/.env.example" "$repo_root/.env"
  echo "Created .env from .env.example"
fi

# Remove bootstrap script before first commit.
rm -f "$repo_root/scripts/bootstrap.sh"

git add .
git commit -m ":tada: initial commit for $project_name"
git branch -M main

if [[ -n "$remote_url" ]]; then
  git remote add origin "$remote_url"
  read -r -p "Push to remote now? [y/N]: " push_now
  push_now="${push_now:-N}"
  if [[ "$push_now" =~ ^[Yy]$ ]]; then
    git push -u origin main
  fi
fi

echo "Done. Project initialized at: $repo_root"
