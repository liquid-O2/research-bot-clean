#!/usr/bin/env bash
# Point Claude, Codex, Cursor overlays, and .agents at the same pstack-lab
# skill tree Grok already reads via Cursor compat. Relative symlinks. No copies.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/.cursor/plugins/pstack-lab/skills"
PLUGIN="$ROOT/.cursor/plugins/pstack-lab"

if [[ ! -d "$SRC" ]]; then
  echo "missing $SRC" >&2
  exit 1
fi

link_dir() {
  local dest="$1"
  local rel="$2"
  mkdir -p "$dest"
  find "$dest" -mindepth 1 -maxdepth 1 -type l -delete
  local name
  for name in "$SRC"/*; do
    [[ -d "$name" ]] || continue
    ln -sfn "$rel/$(basename "$name")" "$dest/$(basename "$name")"
  done
}

link_dir "$ROOT/.cursor/skills" "../plugins/pstack-lab/skills"
link_dir "$ROOT/.claude/skills" "../../.cursor/plugins/pstack-lab/skills"
link_dir "$ROOT/.codex/skills" "../../.cursor/plugins/pstack-lab/skills"
link_dir "$ROOT/.agents/skills" "../../.cursor/plugins/pstack-lab/skills"

mkdir -p "$ROOT/.claude/agents" "$ROOT/.codex/agents"
ln -sfn "../../.cursor/plugins/pstack-lab/agents/poteto-agent.md" "$ROOT/.claude/agents/poteto-agent.md"
ln -sfn "../../.cursor/plugins/pstack-lab/agents/comment-sicko.md" "$ROOT/.claude/agents/comment-sicko.md"
ln -sfn "../../.cursor/plugins/pstack-lab/agents/poteto-agent.md" "$ROOT/.codex/agents/poteto-agent.md"
ln -sfn "../../.cursor/plugins/pstack-lab/agents/comment-sicko.md" "$ROOT/.codex/agents/comment-sicko.md"

echo "linked $(find "$SRC" -mindepth 1 -maxdepth 1 -type d | wc -l) skills into .cursor/skills .claude/skills .codex/skills .agents/skills"
