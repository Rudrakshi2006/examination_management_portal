# EMP — Project tracker

[Architecture](architecture.md) · [Plan](plan.md) · [AI and Git rules](rules.md)

- **Current milestone:** EMP-02 complete; v0.2 Admin setup continues with EMP-03.
- **Next action:** Run the Day 2 browser demo in README.md; begin EMP-03 only when requested.
- **Current blocker:** None recorded.
- **Baseline:** Day 1 is published at `e596650ad38f483e56e57e67d45cc3061ef69b35`. This commit records EMP-02 only; local working files, index and HEAD are preserved.

## Work items

Use **Todo**, **In progress**, **Blocked**, **Ready to verify** or **Done**. Mark Done after the acceptance check passes. Record a commit or PR reference when available.

| ID | Day | Deliverable | Acceptance evidence to record | Status | Commit / PR |
|---|---|---|---|---|---|
| EMP-01 | 1 | Repo, SQLite, login and registration | 14 automated tests pass; detailed Day 1 evidence below | Done | `e596650ad38f483e56e57e67d45cc3061ef69b35` |
| EMP-02 | 2 | Admin home, courses, exams and timing | 15 Day 2 tests pass on each of fresh and Day 1-upgraded databases; all 14 Day 1 tests pass. Counts, CRUD, archival, IST timelines and phase controls verified. | Done | This commit |
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
| 25 Nov 2026 | Not measured | EMP-02 / Day 2 Admin setup | `python -m unittest discover -s tests -v`: final run 44 tests passed in 16.186 seconds (15 fresh + 15 Day 1 upgrade + 14 unchanged Foundation tests). Initial test-helper argument collision fixed; final run has no errors. | — (unstaged, no commit or push) | Manual browser/Mac demo; EMP-03 remains Todo. |

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

### Day 2 verification evidence — 25 November 2026 IST

Verified using Flask's test client / CLI runner, Python 3.11.9 on Windows. Each
Day 2 scenario ran on a fresh temporary database and on a temporary database first
initialized by the Day 1 CLI using the original users-only schema fixture. The
upgrade runs `init-db` twice and compares complete user rows before/after, including
IDs, hashes and statuses. No local runtime database or credentials were changed.

| Check actually run | Result |
|---|---|
| All 14 original Day 1 tests | Pass unchanged, including login, registration, role/status guards, hashing, repeat seed, CSRF and logout. |
| Fresh initialization and Day 1 upgrade | Pass; additive schema works; existing users survive byte-for-byte as row values; existing Admin, Student and Pending Examiner still sign in. |
| Dashboard totals | Course/exam totals include archived rows; Examiner/Student totals match role rows. Absent slots/bookings show labelled zero totals. Synthetic test-only tables also verify nonzero counts when present. |
| Course create/edit/list/delete | Pass; saved names/codes/descriptions render; code normalized; case-insensitive duplicate and invalid fields rejected; unused course deleted. |
| Referenced course removal | Course archived, exam retained and accessible; archived course remains listed with description; archived edits/repeated removal rejected; new exams cannot link to archived course. |
| Exam create/edit/list/detail | Pass; course link, name, duration and marks persist; course can be changed to another active course; all four IST dates and phase render. |
| Timeline validation | Inverted/equal-length/overlapping windows, missing/malformed dates, invalid calendar dates and offset input rejected with saved exam unchanged. Creation end equal to booking start accepted. |
| Field and submitted ID validation | Missing/SQL-like/unknown/oversized course IDs, blank name/type and invalid duration/marks rejected; no invalid exam created. Missing record URLs return 404. |
| Phase controls | Draft, Slot Creation, Booking Open, Closed and Completed persist; unknown phase rejected. At the exact booking-start boundary, Draft/Slot Creation and later creation-end/booking-start edits rejected; safe metadata edit still works. |
| Exam removal and history | Unused Draft exam deleted. Non-Draft exam archived and remains accessible read-only. A synthetic FK-dependent history row prevents Draft deletion and survives archival. |
| Authorization and CSRF | Every Admin GET/POST route denies Students, Pending/Approved Examiners and inactive Admins. Signed-out clients redirect to login. Missing/incorrect CSRF tokens rejected; remove/phase GET requests return 405. |
| Repeat initialization after Day 2 data exists | Users, Admin password, courses and exam data preserved. |

Final result: **44 tests passed, no remaining automated failures**. The first test
run exposed a duplicate `course_id` argument in a test helper; it was corrected.
Review also hardened oversized numeric-ID validation before the final passing run.

Unverified: manual browser visual/mobile layout and macOS shell/demo execution.
Real slot-dependent timeline edits, booking gates and production scheduling records
cannot be exercised until those schemas/features exist in their scheduled phases.
Synthetic tables exist only inside temporary tests. No approval UI, assignments,
rubrics, slots or bookings were implemented. architecture.md records Day 2 storage
and archival choices; plan.md and rules.md remain unchanged and all planning docs
remain at the repository root. Git has no staged files and no commits were made.

### Day 2 release verification — 26 November 2026 IST

Recovered the saved Day 2 tree `a72a2ff546c61bd5e78126f65108fdf4e6556ed0`
and reviewed its delta against the published Day 1 parent. Only this isolated
tracker was updated for the release. `python -m unittest discover -s tests -v`
passed all 44 tests on the isolated snapshot: 14 Foundation tests plus 15 Admin
checks on each of fresh and Day 1-upgraded databases. No Day 3 examiner management,
assignment, rubric or search implementation is included. Existing historical
session entries retain their original dates and outcomes. Manual browser and
macOS execution remain unverified.

## AI use log

Record what Antigravity or Codex actually contributed for the report declaration. Include what you personally ran, reviewed or changed.

| Date | Tool | Contribution | Student verification or edits |
|---|---|---|---|
| 24 Nov 2026 | Codex | Project planning, architecture, tracker and coding rules | Pending |
| 25 Nov 2026 | Codex | Implemented Day 1 Flask app, SQLite/Admin CLI, authentication and guards, CSRF, templates, local Bootstrap/license, tests and README; initialized local Git and ran 14 passing automated tests plus ignore checks. | Student review, macOS setup and manual demo pending; no student-run verification claimed. No commit or push. |
| 25 Nov 2026 | Codex | Implemented EMP-02 Admin counts, course/exam forms and removal/archival, additive schema, IST timelines and phase controls; reused Day 1 guards/CSRF; added fresh/upgrade tests and updated README, architecture and tracker. Ran 44 passing tests including all 14 original tests. | Student review and manual browser/macOS demo pending; no student-run verification claimed. Changes remain unstaged and uncommitted. |
| 26 Nov 2026 | Codex | Recovered the Day 2 snapshot, reviewed the Day 1 delta, updated this milestone-only tracker and ran 44 passing tests in isolation for the Day 2-only commit. | Student review and manual demo pending; no student-run verification claimed. Current working files, index and local HEAD preserved. |
