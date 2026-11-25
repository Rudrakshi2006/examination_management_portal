# EMP — Instructions for Antigravity and Codex

[Architecture](architecture.md) · [Plan](plan.md) · [Tracker](tracker.md)

At the start of a session, read these four files. If the IDE does not automatically load this file, add it to the session context explicitly. Use the current user request and organization statement to resolve scope. Update the relevant project doc whenever an agreed design decision changes.

## Work in verified slices

1. Read the current tracker item, inspect relevant files and check `git status --short`.
2. Implement the requested slice through its real UI route. Reuse existing functions and templates.
3. Run the slice's acceptance checks. Verify both the normal action and the closest failure case. Preserve the existing data and workflows.
4. Update the tracker with what changed, what passed, what remains and any relevant commit or PR. Keep unrelated tracker changes out of the diff.
5. Review staged files before committing. Report actual checks, pending work and assumptions in the handoff.

Use one coding agent at a time on the same branch. Review can be delegated to the other agent once the working diff is stable. Preserve user edits. Avoid broad reformats and unsolicited dependencies.

## Code constraints

- Use Flask, Python sqlite3, Jinja2, HTML, Bootstrap 5 and one custom stylesheet. Bundle Bootstrap CSS locally with its license. Core actions must work through HTML forms without JavaScript.
- Keep Flask route modules organized by role. Use small helpers for shared rules with clear names. Favor code Yash can trace in a viva from form to SQL and back to the rendered page.
- Initialize the SQLite schema and seeded Admin programmatically. Use parameterized SQL, foreign keys, transactions, server-side authorization and validation, hashed passwords and CSRF-protected forms. Keep local secrets and live data out of Git.
- Implement booking, cancellation, reschedule and score changes atomically where multiple records change. Apply phase, time, capacity and ownership checks server-side. Preserve history when archiving or changing records.
- Use fictional demo data and a repeatable local setup. Add targeted regression tests where manual flows cannot reliably verify an important case, such as concurrent final-seat requests.
- Use compact headings, familiar labels, readable tables and modest spacing. Keep the design consistent across Admin, Examiner and Student views. Avoid decorative gradients, animation and filler copy.

## Git and GitHub

- Use a short branch for each coherent feature and keep `main` demo-ready. Avoid parallel edits on the same branch. Review the real diff before staging and stage only paths that belong to the feature.
- One meaningful commit per verified slice is the default. A slice may span days, and related changes may share a commit. Separate fixes only when they are genuine independent changes. There is no daily commit quota.
- Write a short, specific subject that describes what changed. Use plain wording and an imperative verb. A body is useful when the change needs context. Avoid boilerplate like “enhance platform functionality” and vague subjects like “Day 5 update”.
- If the active task authorizes commits, commit after verification. For a review-only request, leave the worktree untouched. Only push, open PRs, merge or tag remote milestones when the session authorizes those actions. Preserve existing Git identity and attribution. Keep timestamps and testing claims accurate.
- Use a short PR summary and list the checks actually performed. For a single logical feature, squash-merge if the repository uses that workflow. Never rewrite shared history, force-push, fabricate activity or split changes just to pad the contribution graph.
- Ignore `.venv/`, `.env`, `instance/`, local SQLite files, caches and packaging output. Track source, templates, static assets, schema and dependency manifests.

| Example subject | When it fits |
|---|---|
| `Set up login and seed the admin account` | Authentication and database bootstrap are verified together |
| `Let students book and cancel exam slots` | Booking and cancellation work through the student UI |
| `Keep booking history when admins move a student` | Rescheduling preserves old and new slot references |
| `Document the local demo setup` | README steps were verified from a clean checkout |

Keep the AI contribution log factual for the report. Commit wording should describe the code clearly. Preserve any attribution that applies to the work.
