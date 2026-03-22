#!/usr/bin/env bash
set -euo pipefail

STATE_DIR=".git/.edit-snapshot"
STATE_FILE="$STATE_DIR/last-session.env"

command_name="${1:-}"
arg="${2:-}"
shift $(( $# > 0 ? 1 : 0 )) || true
reason="${*:-manual edit}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

need_git_repo() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi
  git init -q >/dev/null
}

ensure_identity() {
  if ! git config --get user.name >/dev/null 2>&1; then
    git config user.name "OpenClaw Guard"
  fi
  if ! git config --get user.email >/dev/null 2>&1; then
    git config user.email "openclaw@local.invalid"
  fi
}

ensure_state_dir() {
  mkdir -p "$STATE_DIR"
}

current_head() {
  git rev-parse --short HEAD 2>/dev/null || true
}

current_head_full() {
  git rev-parse HEAD 2>/dev/null || true
}

has_head() {
  git rev-parse --verify HEAD >/dev/null 2>&1
}

worktree_dirty() {
  ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]
}

stage_all() {
  git add -A
}

write_state() {
  cat > "$STATE_FILE" <<STATE
PRE_SHA=${PRE_SHA:-}
POST_SHA=${POST_SHA:-}
REASON=$(printf '%q' "$reason")
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
STATE
}

load_state() {
  if [ -f "$STATE_FILE" ]; then
    # shellcheck disable=SC1090
    source "$STATE_FILE"
    REASON="${REASON:-manual edit}"
    return 0
  fi
  return 1
}

require_pre_state() {
  if ! load_state; then
    fail "no PRE snapshot found for this edit session. Run: $0 pre \"reason\""
  fi
  if [ -z "${PRE_SHA:-}" ]; then
    fail "PRE snapshot state is incomplete. Run: $0 pre \"reason\""
  fi
}

create_commit() {
  local message="$1"
  git commit -m "$message" >/dev/null
}

pre() {
  need_git_repo
  ensure_identity
  ensure_state_dir

  local short_head full_head

  if has_head; then
    if worktree_dirty; then
      stage_all
      if git diff --cached --quiet; then
        full_head="$(current_head_full)"
        short_head="$(current_head)"
        PRE_SHA="$full_head"
        POST_SHA=""
        write_state
        echo "PRE_REUSED $short_head $(git log -1 --pretty=%s)"
        return 0
      fi
      create_commit "guard(pre): $reason"
      full_head="$(current_head_full)"
      short_head="$(current_head)"
      PRE_SHA="$full_head"
      POST_SHA=""
      write_state
      echo "PRE_COMMIT $short_head $(git log -1 --pretty=%s)"
      return 0
    fi

    full_head="$(current_head_full)"
    short_head="$(current_head)"
    PRE_SHA="$full_head"
    POST_SHA=""
    write_state
    echo "PRE_REUSED $short_head $(git log -1 --pretty=%s)"
    return 0
  fi

  if worktree_dirty; then
    stage_all
    if git diff --cached --quiet; then
      git commit --allow-empty -m "guard(init): $reason" >/dev/null
    else
      create_commit "guard(init): $reason"
    fi
  else
    git commit --allow-empty -m "guard(init): $reason" >/dev/null
  fi

  full_head="$(current_head_full)"
  short_head="$(current_head)"
  PRE_SHA="$full_head"
  POST_SHA=""
  write_state
  echo "PRE_INIT $short_head $(git log -1 --pretty=%s)"
}

post() {
  need_git_repo
  ensure_identity
  ensure_state_dir
  require_pre_state

  if worktree_dirty; then
    stage_all
    if git diff --cached --quiet; then
      echo "POST_NONE no staged diff"
      return 0
    fi
    create_commit "guard(post): $reason"
    POST_SHA="$(current_head_full)"
    write_state
    echo "POST_COMMIT $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
    return 0
  fi

  echo "POST_NONE worktree clean"
}

recent() {
  need_git_repo
  local count="${1:-5}"
  if ! [[ "$count" =~ ^[0-9]+$ ]]; then
    count=5
  fi
  if ! has_head; then
    echo "No commits yet"
    return 0
  fi
  git log --date=short --pretty=format:'%h | %ad | %s' -n "$count"
}

rollback_help() {
  need_git_repo
  if load_state; then
    echo "Rollback help"
    if [ -n "${PRE_SHA:-}" ]; then
      echo "PRE_SHA=${PRE_SHA}"
    fi
    if [ -n "${POST_SHA:-}" ]; then
      echo "POST_SHA=${POST_SHA}"
      echo "Preview result diff: git diff ${PRE_SHA}..${POST_SHA}"
      echo "Non-destructive rollback: git revert ${POST_SHA}"
    fi
    if [ -n "${PRE_SHA:-}" ]; then
      echo "Hard rollback to pre-edit snapshot: git reset --hard ${PRE_SHA}"
    fi
    echo "Recovery history: git reflog -n 10"
  else
    echo "No guard session state found. Use: git log --oneline -n 5 && git reflog -n 10"
  fi
}

case "$command_name" in
  pre) pre ;;
  post) post ;;
  recent) recent "$arg" ;;
  rollback-help) rollback_help ;;
  *)
    cat >&2 <<USAGE
Usage:
  $0 pre "reason"
  $0 post "reason"
  $0 recent [count]
  $0 rollback-help
USAGE
    exit 1
    ;;
esac
