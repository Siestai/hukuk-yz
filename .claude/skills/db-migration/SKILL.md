---
name: db-migration
description: Use when changing the database schema in this repo (Alembic migrations under services/app/alembic, ORM models in services/app/app/models, enums, constraints, indexes). Rules for migrations, enums, bitemporal tables and the ORM consistency tests.
---

# db-migration

Schema reference: `docs/data-model.md`. A schema change updates that document in the same PR.

## Migrations

- Files live in `services/app/alembic/versions/`, named `NNNN_<slug>.py`, with `revision = "NNNN"` and `down_revision` set to the previous number. One linear chain, no branches.
- Write migrations by hand, or autogenerate a draft (`make migration name=<slug>`) and then read and fix it. Autogenerate misses enums, partial indexes, exclusion constraints and generated columns.
- The module docstring says what changes and why, with a pointer to the task (`docs/tasks/NN-*.md`).
- Every migration has a working `downgrade()`.
- What Alembic cannot express (`NOT VALID` constraints, `EXCLUDE USING gist`, extensions) goes through `op.execute`, with a comment.
- Never edit a migration that is already on `main`. Add a new one.

## Enums

- Postgres native enums. Type names and labels are ASCII `snake_case` (`source_category`, `genel_yazi`, `duzelterek_onama`). Turkish display text exists only in the UI.
- The migration keeps the labels in a module constant (`ENUMS`, `USER_ROLES`); the ORM enum must match it exactly. Adding a label means a new migration (`ALTER TYPE ... ADD VALUE`) plus the ORM change.

## Bitemporal tables

- Published KB rows are never deleted or updated in place. A new version gets a new row; the old one gets `superseded_at`.
- Two time axes: `valid_from / valid_to` (when the rule was in force, md. 4) and `recorded_at / superseded_at` (when we knew it).
- Uniqueness and overlap rules apply to live rows only: partial unique indexes `WHERE superseded_at IS NULL`, and `EXCLUDE USING gist (... WITH =, daterange(valid_from, valid_to) WITH &&) WHERE (superseded_at IS NULL)` for versioned tables (needs `btree_gist`).
- Personal data (case documents, memory) is the exception: it is deleted by crypto-shredding, not kept (`docs/architecture.md` §6.1).

## Consistency tests

- `services/app/tests/test_orm_consistency.py` checks the ORM against the migrations without a database: enum labels, tables, columns, constraints. Extend it for every new table, enum or migration.
- `services/app/tests/test_schema.py` runs the migrations against Postgres (CI). New constraints get a test that proves they reject bad rows.
- There is no Postgres on the agent server; the DB tests run in CI. Say so in the PR instead of claiming a local run.
