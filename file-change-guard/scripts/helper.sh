#!/usr/bin/env bash
set -euo pipefail

STATE_ROOT=".git/.guarded-edit"
SESSIONS_DIR="$STATE_ROOT/sessions"
CURRENT_SESSION_FILE="$STATE_ROOT/current-session"

SESSION_ID=""
SESSION_DIR=""
STATE_FILE=""
PATHS_FILE=""
SESSION_COMMENT=""

OPEN_SESSION_IDS=()

TARGET_PATHS=()
TARGET_STATUS=""
HAS_STAGED=0
HAS_DIRTY=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
DISTRIBUTED_IGNORE_FILE="$SKILL_DIR/guarded-edit.ignore"
ACTIVE_GUARD_IGNORE=""

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

ensure_state_dirs() {
  mkdir -p "$SESSIONS_DIR"
}

repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd -P
}

active_guard_ignore_file() {
  if [ -f "$DISTRIBUTED_IGNORE_FILE" ]; then
    echo "$DISTRIBUTED_IGNORE_FILE"
    return 0
  fi
  return 1
}

require_paths_not_excluded() {
  [ "$#" -gt 0 ] || return 0

  local ignore_file
  ignore_file="$(active_guard_ignore_file || true)"
  [ -n "$ignore_file" ] || return 0

  local path matched=0 detail
  for path in "$@"; do
    if git -c core.excludesFile="$ignore_file" check-ignore --no-index -q -- "$path"; then
      detail="$(git -c core.excludesFile="$ignore_file" check-ignore --no-index -v -- "$path" 2>/dev/null || true)"
      printf 'EXCLUDED_PATH %s\n' "$path" >&2
      if [ -n "$detail" ]; then
        printf '  %s\n' "$detail" >&2
      fi
      matched=1
    fi
  done

  if [ "$matched" -eq 1 ]; then
    fail "one or more target paths are excluded by active ignore rules. Edit $(printf '%q' "$ignore_file") or choose different target paths."
  fi
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

require_paths() {
  if [ "$#" -eq 0 ]; then
    fail "no target paths provided. Run: $0 pre \"reason\" -- <path> [<path> ...]"
  fi
}

set_session_files() {
  SESSION_DIR="$1"
  STATE_FILE="$SESSION_DIR/state.env"
  PATHS_FILE="$SESSION_DIR/paths.nul"
}

new_session() {
  ensure_state_dirs
  SESSION_DIR="$(mktemp -d "$SESSIONS_DIR/session.XXXXXX")"
  SESSION_ID="$(basename "$SESSION_DIR")"
  set_session_files "$SESSION_DIR"
}

list_open_sessions() {
  OPEN_SESSION_IDS=()
  ensure_state_dirs

  local dir status
  shopt -s nullglob
  for dir in "$SESSIONS_DIR"/session.*; do
    [ -d "$dir" ] || continue
    SESSION_DIR="$dir"
    SESSION_ID="$(basename "$SESSION_DIR")"
    set_session_files "$SESSION_DIR"
    if ! load_state; then
      continue
    fi
    status="${SESSION_STATUS:-open}"
    if [ "$status" = "open" ]; then
      OPEN_SESSION_IDS+=("$SESSION_ID")
    fi
  done
  shopt -u nullglob
}

resolve_default_session() {
  list_open_sessions

  case "${#OPEN_SESSION_IDS[@]}" in
    0)
      [ -f "$CURRENT_SESSION_FILE" ] || fail "no current edit session found. Run PRE first or pass --session <session-id>."
      SESSION_ID="$(cat "$CURRENT_SESSION_FILE")"
      ;;
    1)
      SESSION_ID="${OPEN_SESSION_IDS[0]}"
      ;;
    *)
      fail "multiple open edit sessions exist. Run: $0 sessions 10, then pass --session <session-id>."
      ;;
  esac
}

select_session() {
  local requested_session="${1:-}"

  ensure_state_dirs
  if [ -n "$requested_session" ]; then
    SESSION_ID="$requested_session"
  else
    resolve_default_session
  fi

  SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"
  [ -d "$SESSION_DIR" ] || fail "session not found: $SESSION_ID"
  set_session_files "$SESSION_DIR"
}

set_current_session() {
  printf '%s\n' "$SESSION_ID" > "$CURRENT_SESSION_FILE"
}

paths_file_abs() {
  if [ -f "$PATHS_FILE" ]; then
    echo "$(cd "$(dirname "$PATHS_FILE")" && pwd -P)/$(basename "$PATHS_FILE")"
  else
    echo "$PATHS_FILE"
  fi
}

save_paths() {
  : > "$PATHS_FILE"
  local path
  for path in "$@"; do
    printf '%s\0' "$path" >> "$PATHS_FILE"
  done
}

load_paths() {
  TARGET_PATHS=()
  [ -f "$PATHS_FILE" ] || return 1

  local path
  while IFS= read -r -d '' path; do
    TARGET_PATHS+=("$path")
  done < "$PATHS_FILE"

  [ "${#TARGET_PATHS[@]}" -gt 0 ]
}

refresh_target_status() {
  [ "${#TARGET_PATHS[@]}" -gt 0 ] || fail "internal error: no target paths loaded"

  TARGET_STATUS="$(git status --porcelain=v1 --untracked-files=all -- "${TARGET_PATHS[@]}")"
  HAS_STAGED=0
  HAS_DIRTY=0

  if [ -n "$TARGET_STATUS" ]; then
    HAS_DIRTY=1
  fi

  local line x
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    if [[ "$line" == '?? '* ]]; then
      continue
    fi
    x="${line:0:1}"
    if [ "$x" != " " ]; then
      HAS_STAGED=1
      break
    fi
  done <<< "$TARGET_STATUS"
}

paths_dirty() {
  refresh_target_status
  [ "$HAS_DIRTY" -eq 1 ]
}

staged_changes_present() {
  refresh_target_status
  [ "$HAS_STAGED" -eq 1 ]
}

refuse_if_staged_changes_present() {
  if staged_changes_present; then
    fail "target paths already have staged changes. Refusing to rewrite target-path index state because that can flatten partial staging. Clean, commit, or stash those staged changes first, then run PRE/POST again."
  fi
}

stage_paths() {
  git add -A -- "${TARGET_PATHS[@]}"
}

scoped_staged_diff_exists() {
  ! git diff --cached --quiet -- "${TARGET_PATHS[@]}"
}

write_state() {
  cat > "$STATE_FILE" <<STATE
SESSION_ID=$(printf '%q' "$SESSION_ID")
PRE_SHA=${PRE_SHA:-}
POST_SHA=${POST_SHA:-}
SESSION_STATUS=${SESSION_STATUS:-open}
SESSION_COMMENT=$(printf '%q' "${SESSION_COMMENT:-${SESSION_REASON:-manual edit}}")
REASON=$(printf '%q' "${SESSION_REASON:-${SESSION_COMMENT:-manual edit}}")
REPO_ROOT=$(printf '%q' "$(repo_root)")
PATHS_FILE_ABS=$(printf '%q' "$(paths_file_abs)")
ACTIVE_GUARD_IGNORE=$(printf '%q' "${ACTIVE_GUARD_IGNORE:-}")
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
CLOSED_TS=${CLOSED_TS:-}
STATE
}

load_state() {
  [ -f "$STATE_FILE" ] || return 1
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  SESSION_COMMENT="${SESSION_COMMENT:-${REASON:-manual edit}}"
  REASON="${REASON:-$SESSION_COMMENT}"
  REPO_ROOT="${REPO_ROOT:-$(repo_root)}"
  PATHS_FILE_ABS="${PATHS_FILE_ABS:-$(paths_file_abs)}"
  ACTIVE_GUARD_IGNORE="${ACTIVE_GUARD_IGNORE:-$(active_guard_ignore_file || true)}"
  SESSION_STATUS="${SESSION_STATUS:-open}"
  CLOSED_TS="${CLOSED_TS:-}"
  return 0
}

require_pre_state() {
  if ! load_state; then
    fail "no PRE snapshot found for this edit session. Run: $0 pre \"reason\" -- <path> [<path> ...]"
  fi
  if [ -z "${PRE_SHA:-}" ]; then
    fail "PRE snapshot state is incomplete. Run: $0 pre \"reason\" -- <path> [<path> ...]"
  fi
  if ! load_paths; then
    fail "no stored target paths found for this edit session. Run PRE again with explicit paths."
  fi
  if [ "$(repo_root)" != "$REPO_ROOT" ]; then
    fail "current repo root does not match the stored edit session. Expected: $REPO_ROOT"
  fi
}

create_scoped_commit() {
  local message="$1"
  git commit -m "$message" --only -- "${TARGET_PATHS[@]}" >/dev/null
}

close_session_state() {
  SESSION_STATUS="closed"
  CLOSED_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  write_state
}

print_scope_summary() {
  echo "SESSION $SESSION_ID"
  echo "REPO $(repo_root)"
  echo "STATUS ${SESSION_STATUS:-open}"
  echo "PATHS ${#TARGET_PATHS[@]}"
  if [ -n "${ACTIVE_GUARD_IGNORE:-}" ]; then
    echo "IGNORE_FILE ${ACTIVE_GUARD_IGNORE}"
  fi
}

print_paths() {
  local path
  for path in "${TARGET_PATHS[@]}"; do
    printf '  - %s\n' "$path"
  done
}

pre() {
  SESSION_REASON="$1"
  SESSION_COMMENT="$SESSION_REASON"
  shift || true

  require_paths "$@"
  TARGET_PATHS=("$@")

  need_git_repo
  ensure_identity
  ACTIVE_GUARD_IGNORE="$(active_guard_ignore_file || true)"
  require_paths_not_excluded "${TARGET_PATHS[@]}"
  new_session
  save_paths "${TARGET_PATHS[@]}"

  local short_head full_head

  if has_head; then
    if paths_dirty; then
      refuse_if_staged_changes_present
      stage_paths
      if ! scoped_staged_diff_exists; then
        full_head="$(current_head_full)"
        short_head="$(current_head)"
        PRE_SHA="$full_head"
        POST_SHA=""
        SESSION_STATUS="open"
        CLOSED_TS=""
        set_current_session
        write_state
        echo "PRE_REUSED $short_head $(git log -1 --pretty=%s)"
        print_scope_summary
        return 0
      fi
      create_scoped_commit "guard(pre): $SESSION_REASON"
      full_head="$(current_head_full)"
      short_head="$(current_head)"
      PRE_SHA="$full_head"
      POST_SHA=""
      SESSION_STATUS="open"
      CLOSED_TS=""
      set_current_session
      write_state
      echo "PRE_COMMIT $short_head $(git log -1 --pretty=%s)"
      print_scope_summary
      return 0
    fi

    full_head="$(current_head_full)"
    short_head="$(current_head)"
    PRE_SHA="$full_head"
    POST_SHA=""
    SESSION_STATUS="open"
    CLOSED_TS=""
    set_current_session
    write_state
    echo "PRE_REUSED $short_head $(git log -1 --pretty=%s)"
    print_scope_summary
    return 0
  fi

  if paths_dirty; then
    refuse_if_staged_changes_present
    stage_paths
    if ! scoped_staged_diff_exists; then
      git commit --allow-empty -m "guard(init): $SESSION_REASON" >/dev/null
    else
      create_scoped_commit "guard(init): $SESSION_REASON"
    fi
  else
    git commit --allow-empty -m "guard(init): $SESSION_REASON" >/dev/null
  fi

  full_head="$(current_head_full)"
  short_head="$(current_head)"
  PRE_SHA="$full_head"
  POST_SHA=""
  SESSION_STATUS="open"
  CLOSED_TS=""
  set_current_session
  write_state
  echo "PRE_INIT $short_head $(git log -1 --pretty=%s)"
  print_scope_summary
}

post() {
  SESSION_REASON="$1"
  local requested_session="${2:-}"

  need_git_repo
  ensure_identity
  ensure_state_dirs
  select_session "$requested_session"
  require_pre_state
  SESSION_COMMENT="${SESSION_COMMENT:-${REASON:-manual edit}}"

  if paths_dirty; then
    refuse_if_staged_changes_present
    stage_paths
    if ! scoped_staged_diff_exists; then
      close_session_state
      echo "POST_NONE no staged diff for stored paths"
      print_scope_summary
      return 0
    fi
    create_scoped_commit "guard(post): $SESSION_REASON"
    POST_SHA="$(current_head_full)"
    close_session_state
    echo "POST_COMMIT $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
    print_scope_summary
    return 0
  fi

  close_session_state
  echo "POST_NONE no changes in stored paths"
  print_scope_summary
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

  local current=""
  if [ -f "$CURRENT_SESSION_FILE" ]; then
    current="$(cat "$CURRENT_SESSION_FILE")"
  fi

  if [ -n "$current" ] && [ -d "$SESSIONS_DIR/$current" ]; then
    SESSION_ID="$current"
    SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"
    set_session_files "$SESSION_DIR"
    if load_state && load_paths; then
      recent_paths "$count"
      return 0
    fi
  fi

  git log --date=short --pretty=format:'%h | %ad | %s' -n "$count"
}

recent_paths() {
  local count="$1"
  if [ "${#TARGET_PATHS[@]}" -eq 0 ]; then
    echo "No target paths"
    return 0
  fi
  if ! git log --date=short --pretty=format:'%h | %ad | %s' -n "$count" -- "${TARGET_PATHS[@]}" 2>/dev/null; then
    echo "No commits yet for target paths"
  fi
}

sessions() {
  ensure_state_dirs
  local count="${1:-5}"
  if ! [[ "$count" =~ ^[0-9]+$ ]]; then
    count=5
  fi

  local current=""
  if [ -f "$CURRENT_SESSION_FILE" ]; then
    current="$(cat "$CURRENT_SESSION_FILE")"
  fi

  local dir shown=0 mark
  for dir in $(ls -1dt "$SESSIONS_DIR"/session.* 2>/dev/null || true); do
    [ -d "$dir" ] || continue
    SESSION_DIR="$dir"
    SESSION_ID="$(basename "$SESSION_DIR")"
    set_session_files "$SESSION_DIR"
    if ! load_state; then
      continue
    fi
    mark=" "
    if [ "$SESSION_ID" = "$current" ]; then
      mark="*"
    fi
    printf '%s %s | %s | %s | comment=%s | pre=%s | post=%s\n' \
      "$mark" \
      "$SESSION_ID" \
      "$TS" \
      "$SESSION_STATUS" \
      "${SESSION_COMMENT:-${REASON:-manual edit}}" \
      "${PRE_SHA:0:12}" \
      "${POST_SHA:-none}"
    shown=$((shown + 1))
    if [ "$shown" -ge "$count" ]; then
      break
    fi
  done

  if [ "$shown" -eq 0 ]; then
    echo "No saved edit sessions"
  fi
}

rollback_help() {
  local requested_session="${1:-}"

  need_git_repo
  ensure_state_dirs
  select_session "$requested_session"

  if ! load_state; then
    echo "No guard session state found. Use: git log --oneline -n 5 && git reflog -n 10"
    return 0
  fi
  if ! load_paths; then
    fail "session exists but target paths could not be loaded"
  fi

  echo "Rollback help"
  echo "SESSION_ID=${SESSION_ID}"
  echo "REPO_ROOT=${REPO_ROOT}"
  echo "SESSION_STATUS=${SESSION_STATUS}"
  echo "SESSION_COMMENT=${SESSION_COMMENT:-${REASON:-manual edit}}"
  echo "TARGET_PATHS=${#TARGET_PATHS[@]}"
  print_paths
  echo "PATHS_FILE=${PATHS_FILE_ABS}"
  if [ -n "${ACTIVE_GUARD_IGNORE:-}" ]; then
    echo "ACTIVE_GUARD_IGNORE=${ACTIVE_GUARD_IGNORE}"
  fi
  if [ -n "${PRE_SHA:-}" ]; then
    echo "PRE_SHA=${PRE_SHA}"
  fi
  if [ -n "${POST_SHA:-}" ]; then
    echo "POST_SHA=${POST_SHA}"
    echo "Preview result diff for stored paths: git diff ${PRE_SHA}..${POST_SHA} --pathspec-from-file=$(printf '%q' "$PATHS_FILE_ABS") --pathspec-file-nul"
    echo "History-preserving undo of the post commit: git revert ${POST_SHA}"
  fi
  if [ -n "${PRE_SHA:-}" ]; then
    echo "Safest path-scoped rollback to the pre-edit snapshot: git restore --source=${PRE_SHA} --staged --worktree --pathspec-from-file=$(printf '%q' "$PATHS_FILE_ABS") --pathspec-file-nul"
  fi
  echo "Recovery history: git reflog -n 10"
}

report() {
  need_git_repo
  ensure_state_dirs

  local count="${1:-5}"
  if ! [[ "$count" =~ ^[0-9]+$ ]]; then
    count=5
  fi

  recent "$count"
}

parse_optional_session_arg() {
  OPTIONAL_SESSION_ID=""
  if [ "$#" -eq 0 ]; then
    return 0
  fi
  if [ "$1" = "--session" ]; then
    [ "$#" -ge 2 ] || fail "missing session id after --session"
    OPTIONAL_SESSION_ID="$2"
    [ "$#" -eq 2 ] || fail "unexpected extra arguments"
    return 0
  fi
  fail "unexpected arguments"
}

command_name="${1:-}"
shift || true

case "$command_name" in
  pre)
    reason="${1:-manual edit}"
    shift || true
    if [ "${1:-}" = "--" ]; then
      shift
    fi
    pre "$reason" "$@"
    ;;
  post)
    reason="${1:-manual edit}"
    shift || true
    parse_optional_session_arg "$@"
    post "$reason" "$OPTIONAL_SESSION_ID"
    ;;
  report)
    report "${1:-5}"
    ;;
  recent)
    recent "${1:-5}"
    ;;
  sessions)
    sessions "${1:-5}"
    ;;
  rollback-help)
    parse_optional_session_arg "$@"
    rollback_help "$OPTIONAL_SESSION_ID"
    ;;
  *)
    cat >&2 <<USAGE
Usage:
  $0 pre "reason" -- <path> [<path> ...]
  $0 post "reason" [--session <session-id>]
  $0 recent [count]
  $0 sessions [count]
  $0 report [count]
  $0 rollback-help [--session <session-id>]
USAGE
    exit 1
    ;;
esac
