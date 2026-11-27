-- Additive initialization: never drop existing tables or accounts.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin', 'Student', 'Examiner')),
    status TEXT NOT NULL,
    contact TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    CHECK (
        (role IN ('Admin', 'Student') AND status IN ('Active', 'Inactive'))
        OR (role = 'Examiner' AND status IN ('Pending', 'Approved', 'Inactive'))
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS one_admin ON users (role) WHERE role = 'Admin';

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(code)) BETWEEN 1 AND 30),
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
);

-- Canonical YYYY-MM-DDTHH:MM timestamps, all in IST (UTC+05:30).
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    exam_type TEXT NOT NULL CHECK (length(trim(exam_type)) BETWEEN 1 AND 50),
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 1 AND 1440),
    maximum_marks INTEGER NOT NULL CHECK (maximum_marks BETWEEN 1 AND 10000),
    creation_start TEXT NOT NULL,
    creation_end TEXT NOT NULL,
    booking_start TEXT NOT NULL,
    booking_end TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'Draft' CHECK (phase IN ('Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    published_at TEXT,
    CHECK (creation_start < creation_end AND creation_end <= booking_start AND booking_start < booking_end)
);
CREATE INDEX IF NOT EXISTS exams_course ON exams(course_id);

CREATE TABLE IF NOT EXISTS examiner_assignments (
    exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE RESTRICT,
    examiner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    PRIMARY KEY (exam_id, examiner_id)
);

CREATE TABLE IF NOT EXISTS rubrics (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE RESTRICT,
    name TEXT NOT NULL COLLATE NOCASE CHECK (length(trim(name)) BETWEEN 1 AND 100),
    maximum_marks INTEGER NOT NULL CHECK (maximum_marks BETWEEN 1 AND 10000),
    description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
    UNIQUE (exam_id, name)
);
