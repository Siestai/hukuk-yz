---
name: task-pr-hygiene
description: Use when writing a task spec under docs/tasks, implementing a task, committing, or preparing a pull request in this repo. Rules for spec format, scope, test layout and what a PR may contain.
---

# task-pr-hygiene

## Task specs (`docs/tasks/NN-<slug>.md`)

- Written in Turkish. Header lines: `Durum`, `Sahip`, `Onay: Orhan`, `Bağlam` (the docs and earlier tasks it builds on).
- Sections: `Hedef`, `Kapsam`, `Kapsam dışı`, `Kabul kriterleri`, and `Notlar Claude Code için` where useful.
- Acceptance criteria are commands or checks someone can run, not wishes.
- The spec is merged before the implementation starts. Decisions taken while writing it go to `docs/decisions.md` in the same PR.

## Implementing

- Do what the spec says. Anything outside `Kapsam` is not added, even if it looks useful: write it in the PR description as a follow-up instead.
- No dead code, no commented-out code, no duplicate helpers. Move shared logic instead of copying it (task 09 moved the queue query into `app.kb` rather than duplicating it).
- Run `make lint`, `make typecheck`, `make test` before saying a task is done.

## Tests

- Test files are named after the module they test: `test_detect.py`, `test_review.py`, `test_kb.py`.
- Never name a test file after a process: no `test_review_fixes.py`, `test_task09.py`, `test_round2.py`. Fixes from a review round go into the existing module's test file.
- No duplicate tests; extend the existing one.

## Commits and PRs

- Commit and PR titles in English, conventional style: `feat(app): ...`, `docs: ...`, `fix(ingest): ...`. Task PRs name the task: `feat(app): decision review API (task 09)`.
- Commit locally. Do not push: the agent that started you pushes and opens the PR.
- PR description: what changed, how each acceptance criterion was checked (with output), and what could not be verified here (for example, Docker or Postgres tests that only run in CI).
- Never commit `data/`, `.env*` (except `.env.example`), tokens, server addresses, phone numbers or allowlists. The repo is public.
- Merging is always Orhan's.
