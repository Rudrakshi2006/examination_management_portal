# EMP — Project tracker

[Architecture](architecture.md) · [Plan](plan.md) · [AI and Git rules](rules.md)

- **Current milestone:** v0.1 Foundation
- **Next action:** Run the macOS demo steps in README.md; then begin EMP-02 when requested.
- **Current blocker:** None recorded.
- **Baseline:** EMP-01 implemented and verified with Flask's test client. Git initialized on `foundation`; no files staged, committed or pushed.

## Work items

Use **Todo**, **In progress**, **Blocked**, **Ready to verify** or **Done**. Mark Done after the acceptance check passes. Record a commit or PR reference when available.

| ID | Day | Deliverable | Acceptance evidence to record | Status | Commit / PR |
|---|---|---|---|---|---|
| EMP-01 | 1 | Repo, SQLite, login and registration | 14 automated tests pass; detailed Day 1 evidence below | Done | — (not committed) |
| EMP-02 | 2 | Admin home, courses, exams and timing | Counts match data. CRUD and phase gates work. Historical exam survives archival. | Todo | — |
| EMP-03 | 3 | People, assignment, rubrics and admin search | Approve a request, assign examiner, save 30-mark rubric, find people and exams by name/ID. | Todo | — |
| EMP-04 | 4 | Examiner slots and rosters | Create within window, reject overlap, reject edits after booking starts, scope roster to owner. | Todo | — |
| EMP-05 | 5 | Student dashboard, bookings, history and profile | Search/filter, book, cancel and rebook. History and profile persist. | Todo | — |
| EMP-06 | 6 | Admin slots/bookings and overrides | Search bookings by name/ID, reschedule with seat transfer and replace examiner. | Todo | — |
| EMP-07 | 7 | Evaluation and results | Authorized examiner awards 25/30. Student sees own result only after publication. | Todo | — |
| EMP-08 | 8 | QA, responsive UI and offline demo | Acceptance checklist run. Core failures resolved. Bootstrap loads without network. | Todo | — |
| EMP-09 | 9 | README, demo data and report | Fresh setup follows README. Report is ≤5 pages with accurate ER diagram and AI declaration. | Todo | — |
| EMP-10 | 9–10 | Video, ZIP and release | Drive link opens incognito. Extracted ZIP runs. Archive matches tagged source and submission confirmed. | Todo | — |

## Acceptance checklist

- [x] Admin exists after initialization and cannot self-register. Pending and inactive examiners cannot operate the dashboard.
- [ ] Students and examiners cannot bypass role checks using direct URLs or submitted IDs. Day 1 direct-URL and submitted role/status checks passed; object-ID checks await later features.
- [ ] Examiner slot creation and Student booking reject requests outside the configured phases and windows.
- [ ] Capacity-1 slot becomes Full after booking. Two requests for the final seat yield one confirmed booking.
- [ ] A student cannot book two slots for the same exam. Cancellation releases a seat and retains history. Late cancellation fails.
- [ ] Admin can reschedule to an eligible future slot. A failed move leaves the original booking intact.
- [ ] Admin can replace an examiner with an approved, assigned examiner who has no scheduling conflict.
- [ ] Examiner cannot score another examiner's booking. Out-of-range scores fail and valid rubric scores total correctly.
- [ ] Published marks and remarks are visible to the correct student. Unpublished results remain hidden.
- [ ] Fresh install, offline styling, ZIP extraction and all three role demos work locally.

## Session log

Append one row per actual session. Use calendar dates in IST. Enter only checks you ran. Record a blocker here with the next action if you cannot resolve it in-session.

| Date | Time spent | Items worked on | Verification / result | Commit or PR | Next action |
|---|---:|---|---|---|---|
| 25 Nov 2026 | Not measured | EMP-01 / v0.1 Foundation | `python -m unittest discover -s tests -v`: 14 tests passed on Windows / Python 3.11.9. Git ignore rules checked. Initial missing CLI app context fixed; two test-helper errors corrected before final passing run. | — (no commit or push) | User runs macOS demo; EMP-02 remains Todo. |

### Day 1 verification evidence — 25 November 2026 IST

All checks below ran through Flask's test client / CLI runner against fresh temporary
SQLite databases. The temporary approval/deactivation changes did not touch a local
demo database. Final run: **14 tests, OK**; no remaining automated failures.

| Check actually run | Result |
|---|---|
| Initialize twice, with a changed bootstrap password on second run | Exactly one Admin; original password hash still verifies; existing Student preserved. |
| Seeded Admin signs in | Redirects to Admin dashboard and page renders. |
| Public Admin registration and submitted role/status tampering | Admin registration GET/CSRF-valid POST return 404; Student stays Active Student; Examiner stays Pending Examiner; one Admin remains. |
| Student registers and signs in | Registration succeeds and Student dashboard renders. |
| Examiner registers and signs in while Pending | Approval-pending page renders; direct Examiner dashboard URL returns 403. |
| Examiner approved in temporary database | Dashboard renders; subsequent login redirects there. |
| Examiner deactivated in temporary database | Existing session immediately denied dashboard/pending page; new login reports inactive account. |
| Signed-out and wrong-role requests | All role dashboards redirect signed-out clients to login; cross-role requests return 403. |
| Duplicate registration and incorrect credentials | Case/whitespace-normalized duplicate rejected with clear message; wrong password, unknown email and SQL-like input rejected. |
| Server-side registration validation | Invalid name/email/password, confirmation mismatch and oversized contact/department rejected without creating users. |
| CSRF and logout | Missing, incorrect and non-ASCII invalid CSRF tokens rejected on every POST route; GET logout rejected; valid POST logout clears access. |
| SQLite constraints and connection configuration | Foreign keys enabled; second Admin, invalid roles and invalid role/status combinations rejected. |
| Offline styling assets | Local Bootstrap 5.3.3 CSS and custom CSS return 200; upstream MIT license bundled. |
| Git exclusions | `git check-ignore` confirms virtual environment, `.env`, private config, database, WAL and Python cache paths ignored. |

Unverified: macOS shell setup, a clean dependency installation, browser visual/mobile
layout and a manual browser demo. No future-milestone feature checks ran. The original
planning documents remain at the root; architecture.md, plan.md and rules.md are unchanged.

## AI use log

Record what Antigravity or Codex actually contributed for the report declaration. Include what you personally ran, reviewed or changed.

| Date | Tool | Contribution | Student verification or edits |
|---|---|---|---|
| 24 Nov 2026 | Codex | Project planning, architecture, tracker and coding rules | Pending |
| 25 Nov 2026 | Codex | Implemented Day 1 Flask app, SQLite/Admin CLI, authentication and guards, CSRF, templates, local Bootstrap/license, tests and README; initialized local Git and ran 14 passing automated tests plus ignore checks. | Student review, macOS setup and manual demo pending; no student-run verification claimed. No commit or push. |
