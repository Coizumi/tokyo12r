# Repository Rules

## Scope

These rules apply to the TOKYO12R repository under this directory.

## Source of Truth

- Treat `specs.md` as the primary project specification for TOKYO12R.
- Before changing application behavior, infrastructure, deployment, scheduling, prediction logic, result rendering, or documentation, read the relevant section of `specs.md`.
- If implementation and `specs.md` conflict, do not silently choose one. Update the implementation to match `specs.md`, or update `specs.md` in the same change when the requested behavior intentionally changes the specification.
- Keep `introduce.md` aligned when operational setup, VPS deployment, keys, firewall policy, systemd, or WebARENA procedures change.

## Infrastructure and Deployment

- TOKYO12R infrastructure is documented in `specs.md`, including the WebARENA Indigo VPS, Cloudflare Workers Cron, GitHub Actions, and Cloudflare Pages relationship.
- Do not move heavy data collection or historical recalculation into GitHub Actions unless `specs.md` is explicitly changed to allow it.
- VPS-side batch execution should remain on WebARENA Indigo unless the infrastructure section of `specs.md` is changed.
- Cloudflare Worker secrets, WebARENA API credentials, GitHub tokens, and SSH private keys must not be committed.

## SQLite Execution

- Do not run SQLite on the Windows host in this workspace.
- If a task needs SQLite, run it inside the Hyper-V `al10` environment or on the intended Linux VPS.
- This includes direct `sqlite3` calls and indirect SQLite use through Python, Node, or other bindings.

## Change Discipline

- Keep code changes scoped to the requested behavior and the relevant specification section.
- When changing user-visible behavior, update `specs.md` in the same commit.
- When changing VPS/systemd/Cloudflare operation, update both `specs.md` and the relevant deployment documentation.
- Do not revert user changes or unrelated local changes.
