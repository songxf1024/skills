---
name: edit-snapshot
description: Mandatory before any workspace write. Use before creating a file, script, config, test, or document; editing, patching, overwriting, refactoring, renaming, moving, or deleting files; generating code or artifacts; changing configs; or running write-capable shell commands. Do not skip for small tasks. Create a local git snapshot before the first write, then show recent history and rollback guidance after the change.
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["git"],"anyBins":["bash","sh"]},"emoji":"🛟"}}
---

# Edit Snapshot

If you are about to create, edit, patch, overwrite, rename, move, or delete any workspace file, stop and use this skill before the first write.

Use this skill whenever the current task might write, create, overwrite, rename, delete, or otherwise mutate workspace files.

This is a safety skill.
Do not decide based on perceived risk, task size, or how easy the file would be to recreate.
Prefer using it too often rather than skipping it when a write is about to happen.
Even small or simple tasks such as creating one script, updating one config value, or applying one quick patch should use it before the first mutation.

## What this skill does

This skill adds a lightweight git safety layer around file changes.

Before the first write, it creates or records a recovery point.
After the task finishes, it records the result when needed, shows recent commits, and tells the user that rollback is available.

## High-priority trigger cues

Treat these as mechanical trigger cues, not judgment calls.
Use this skill before the first mutation for any task that includes signals like these:

- create a file, script, config, test, migration, or document
- edit, update, modify, change, patch, rewrite, or overwrite a file
- apply_patch or any multi-file patching workflow
- refactor, rename, move, or delete files
- generate code, templates, artifacts, or outputs into the workspace
- run shell commands that write files, change configs, or regenerate outputs
- make "just a small change" or "just create a quick script"

If the task might write files and you are unsure, use this skill.
False positives are acceptable. Missing the safety snapshot is worse.

## When to use it

Use this skill for tasks such as:

- editing existing files
- creating new files
- deleting or renaming files
- refactoring code
- changing configuration files
- applying patches
- running shell commands that mutate the workspace
- generating code or other files

Do not use it for read-only inspection, explanation-only tasks, search, grep, or diff-only review.

## Task rule

For one user request, create one PRE snapshot before the first mutation.
Do not skip PRE just because the task looks trivial, low-risk, easy to redo, or limited to one small file.

Do not create a new PRE snapshot before every file in the same task.
Only start a new PRE snapshot when the previous edit batch is already finished and reported.

## Required workflow

### 1. Before the first write

Run:

```bash
{baseDir}/scripts/helper.sh pre "<short reason>"
```

Examples:

- `fix login validation`
- `refactor config loader`
- `create weather query script`
- `update skill metadata`

### 2. Perform the edits

Modify files normally.

### 3. Validate if needed

Run tests, linters, type checks, or a focused sanity check when the task warrants it.

### 4. After the edits finish

Run:

```bash
{baseDir}/scripts/helper.sh post "<short reason>"
{baseDir}/scripts/helper.sh recent 5
{baseDir}/scripts/helper.sh rollback-help
```

### 5. Report back to the user

Always tell the user:

- what the PRE snapshot is
- whether a POST commit was created
- the repo root that was used
- the most recent 3 to 5 commits
- that rollback is supported
- the safest rollback command for this task

## Reporting template

```text
已完成本次修改，并已做 git 保护。

仓库: <repo_root>
PRE 快照: <sha> <subject>
POST 快照: <sha or none> <subject or reason>
最近提交:
<recent output>

支持回退。
如需回到本次修改前，优先使用:
  git reset --hard <pre_sha>
如需查看还能恢复到哪里，可用:
  git reflog -n 10
```

If a POST commit exists and the user may prefer a non-destructive rollback, also mention:

```bash
git revert <post_sha>
```

## Behavior rules

- If the current directory is not a git repository, initialize one automatically.
- If git identity is missing, set repo-local `user.name` and `user.email`.
- Respect `.gitignore`.
- Non-ignored new files, generated artifacts, binaries, and accidentally placed sensitive files may also be included in the snapshot.
- Never push unless the user explicitly asked.
- Never rewrite history unless the user explicitly asked.
- Never hide failures.
- If PRE fails, stop risky edits and tell the user.
- If no PRE snapshot exists for the current edit session, do not run POST silently.
- Say which repo root was used so the user can see where the snapshot was recorded.

## Commit policy

### PRE step

- If the repo already has a clean `HEAD`, reuse it as the recovery point.
- If there are uncommitted changes, commit them as a PRE snapshot.
- If there is no `HEAD` yet, create an initial anchor commit when needed.

### POST step

- Only run POST after a valid PRE snapshot for the same edit session exists.
- If the task produced new changes, commit them as a POST snapshot.
- If nothing changed after the task, report that no POST commit was needed.

This keeps history useful without creating unnecessary empty commits.

## Preferred commands

```bash
{baseDir}/scripts/helper.sh pre "reason"
{baseDir}/scripts/helper.sh post "reason"
{baseDir}/scripts/helper.sh recent 5
{baseDir}/scripts/helper.sh rollback-help
```

## Fallback manual commands

If the helper script is unavailable, use:

```bash
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -q
if ! git config user.name >/dev/null 2>&1; then git config user.name "OpenClaw Guard"; fi
if ! git config user.email >/dev/null 2>&1; then git config user.email "openclaw@local.invalid"; fi

git add -A
if ! git diff --cached --quiet; then git commit -m "guard(pre): <reason>"; fi

# ...perform edits...

git add -A
if ! git diff --cached --quiet; then git commit -m "guard(post): <reason>"; fi

git log --oneline -n 5
git reflog -n 10
```
