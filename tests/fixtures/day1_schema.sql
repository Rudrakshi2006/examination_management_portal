-- Original Day 1 schema, retained solely as an upgrade-test fixture.
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
