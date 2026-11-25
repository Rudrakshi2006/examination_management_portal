# EMP — 10-day implementation plan

[Architecture](architecture.md) · [Tracker](tracker.md) · [AI and Git rules](rules.md)

Start on **24 November 2026 IST**. Target submission on **3 December 2026**, assuming ten calendar days from the plan start. Budget about **15 hours** across daily sessions of 1–2 hours. Use Antigravity to implement and run the app locally. Use Codex for a focused diff review or debugging when needed.

| Day | Phase | Time | Work and acceptance gate |
|---|---|---:|---|
| 1 · 24 Nov | Foundation | 1.5 h | Initialize GitHub repo and ignore runtime files. Build Flask startup, SQLite schema, Admin seed, login and registration. Verify fresh initialization, Student login and pending Examiner screen. |
| 2 · 25 Nov | Admin setup | 1.5 h | Build dashboard counts, Course/Exam CRUD and timeline/phase forms. Verify exam setup and reject inverted or overlapping phase windows. |
| 3 · 26 Nov | Admin setup | 1.5 h | Add examiner approval, deactivation, direct creation and assignment. Build rubric CRUD and People/Exams search. Verify 30-mark rubric and approved examiner assignment. |
| 4 · 27 Nov | Slots | 1.5 h | Add examiner dashboard, slot creation/edit/removal, roster and Admin all-slots view. Verify date/phase gates, roster ownership and collision rejection. |
| 5 · 28 Nov | Bookings | 2 h | Add exam search/filter, student dashboard, booking, cancellation, schedule, history and profile. Verify last seat, duplicate rejection, cancellation and rebooking. |
| 6 · 29 Nov | Admin overrides | 1.5 h | Add global booking search, reschedule, replacement examiner and historical views. Verify seat moves, history and replacement eligibility. |
| 7 · 30 Nov | Results | 1.5 h | Build rubric scoring, remarks, completion and publication. Verify a student's 25/30 with remarks appears only after publication. |
| 8 · 1 Dec | QA and UI | 1.5 h | Run the tracker checks, fix failures, verify mobile tables and offline CSS. Complete core defects before optional polish. |
| 9 · 2 Dec | Report and video | 1.5 h | Finish README, demo seed, report and walkthrough video. Run fresh setup before recording. |
| 10 · 3 Dec | Submission | 1 h | Add the accessible Drive link, verify extracted ZIP, compare to Git revision, tag and submit the required files. |

## Version checkpoints

| Version | Target | Release gate |
|---|---|---|
| v0.1 | Day 1 | Install, initialize and exercise all three authentication paths |
| v0.2 | Day 3 | Admin configures a complete exam with an approved examiner and rubric |
| v0.3 | Day 5 | Examiner creates a slot and Student can book or cancel it |
| v0.4 | Day 7 | Admin overrides, evaluator and publication work end-to-end |
| v1.0.0 | Day 10 | Verified ZIP, report and video link ready for submission |

Intermediate versions are planning labels. Tag the verified submission revision. A version checkpoint does not require an extra commit.

## Session rhythm

For a 90-minute session, spend 10 minutes selecting a tracker item, 45 implementing, 20 testing, 10 explaining the flow and 5 recording progress or committing. With one hour, focus on one acceptance gate. Move unfinished work forward in the tracker with the actual status. Use Day 8 to recover core feature slip. Skip the optional print scorecard, charts, emails and JSON API if any core gate is outstanding.

## Submission and viva

- Submit a single source ZIP per the organization's packaging instructions. Include code, templates, static assets, schema, dependency manifest and README. Exclude local secrets, runtime database, virtual environment, caches and Git metadata.
- Submit the report in at most five pages. Include student details, problem statement, approach, frameworks/libraries, schema-matched ER diagram, API endpoints if implemented, actual AI use and the Drive video link.
- Aim for a five-minute recording. Cover intro in about 30 seconds, approach in 30, key features in at least 90 and any optional feature in about 30. Use the remaining time to show the three-role flow and the important constraints. Verify the Drive link in an incognito window with Anyone with the link access.
- For viva, rehearse changing the capacity limit, adding an exam type filter and splitting examiner counts by approval status. Explain the form, route, SQL and template involved. Repeat the full demo once after submission and once before viva.
