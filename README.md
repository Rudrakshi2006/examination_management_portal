# Examination Management Portal — v0.1 Foundation

Day 1 implements SQLite initialization, one locally configured Admin, Student and
Examiner registration, login/logout and protected dashboard placeholders. Students
are Active immediately. Examiners start Pending; only Approved examiners can use
their dashboard. Approval UI and all exam-management features belong to later days.

## macOS setup and quick demo

Use Python 3.11 or newer. In Terminal, change into this repository, then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p instance
python -c 'import getpass, pathlib, secrets; p = pathlib.Path("instance/config.py"); assert not p.exists(), "Local config already exists; edit it instead"; email = input("Admin email: ").strip(); password = getpass.getpass("Admin password (8–128 characters): "); p.write_text("SECRET_KEY = " + repr(secrets.token_hex(32)) + "\nADMIN_NAME = " + repr("Local Administrator") + "\nADMIN_EMAIL = " + repr(email) + "\nADMIN_PASSWORD = " + repr(password) + "\n"); p.chmod(0o600)'
python -m flask --app app init-db
python -m flask --app app init-db
python -m flask --app app run --port 5000
```

Open [the local portal](http://127.0.0.1:5000). Sign in using the Admin credentials
you just entered. Sign out, register a Student, then sign in to see its dashboard.
Sign out and repeat with an Examiner to see the approval-pending page.

The configuration command refuses to overwrite an existing file. For manual
configuration, copy `config.example.py` to `instance/config.py`, fill in all four
settings and generate a secret with `python -c 'import secrets; print(secrets.token_hex(32))'`.
Keep `instance/config.py` private; it and the database are ignored by Git. Never
use the example with empty settings. The database defaults to `instance/emp.sqlite3`.
Changing bootstrap credentials does not alter an existing Admin. After the first
initialization you may remove `ADMIN_PASSWORD` from local configuration.

For later demo sessions:

```sh
source .venv/bin/activate
python -m flask --app app run --port 5000
```

The Flask server is for local development. Bootstrap 5.3.3 CSS and its MIT license
are bundled in `static/vendor/`; pages need no CDN or JavaScript.

## Repeatable verification

```sh
python -m unittest discover -s tests -v
```

Tests use fresh temporary SQLite files, random test secrets and Flask's test client.
They do not modify your local accounts. They cover repeat initialization and
password preservation, registration, role/status enforcement, temporary database
approval and deactivation, validation, CSRF, logout and local CSS delivery.
macOS shell setup and visual browser layout require a local manual check.

## Viva: form → route → database → page

- `app.py:create_app` loads private configuration, registers the role Blueprints
  and checks POST CSRF tokens in `protect_forms`.
- `db.py:get_db` opens one SQLite connection per request and enables foreign keys.
  `init_db_command` applies `schema.sql` without dropping data, checks for an
  existing Admin and hashes the initial password with Werkzeug.
- `auth.py:register_student` and `register_examiner` call `register` with a fixed
  role. It validates the form, hashes the password and inserts through parameterized
  SQL. The schema rejects duplicate email addresses and invalid roles/statuses.
- `auth.py:login` looks up the normalized email, checks the hash and account status,
  clears the old session, stores the user ID and redirects via `dashboard_url`.
  The session also holds a CSRF token, but no role, status or password.
- `auth.py:load_logged_in_user` reloads the account on every request;
  `role_required` checks its current role and status before the dashboard handlers
  in `admin.py`, `student.py` and `examiner.py` run. Pending examiners use
  `examiner.py:pending`; direct dashboard access returns 403.
- Templates extend `templates/base.html`. `auth.py:logout` clears the session
  after a CSRF-protected POST.

Planning documents remain at the repository root. See `tracker.md` for checks
actually run and AI contributions.
