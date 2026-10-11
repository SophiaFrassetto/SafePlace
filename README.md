# SafeSpace

SafeSpace is a Django application for a private account, diary, health profile,
and emergency-information workspace.

## Local setup

The checked-in `.env.example` is a development template, not a production
configuration. Copy it to `.env`, generate a unique `SECRET_KEY`, and keep the
file private. Install dependencies and create the local schema:

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

`SECRET_KEY` is required at startup. The example intentionally leaves it blank
so an unset key cannot silently become a deployment secret.

## Backend status

- Email/password account creation, login, logout, and Django's password-reset
  flow are connected. Password reset uses the console mail backend only for
  local development; configure SMTP credentials through environment variables
  before deployment.
- Account, diary, health, medication, emergency-contact, crisis-instruction,
  and SOS-preference models use UUID primary keys and owner-oriented indexes.
- General profile information, health information, medications, emergency
  contacts, crisis instructions, password changes, and SOS sharing choices are
  persisted through authenticated, CSRF-protected forms.
- Profile photos are cropped to a square in the browser, validated on upload,
  stored in private media, and shown on public SOS cards only when explicitly
  shared.
- SOS cards use locally generated QR images and signed, revocable bearer links.
  The vertical ID-1 front/back card uses label-and-text fields without text
  boxes; its front includes name, contacts, photo, address, and a QR code. The
  back gives more room to medications and crisis instructions. The QR opens a
  styled digital information page, not the printable card. The name is always
  included; other fields, including address and profile photo, are enabled by
  default for new preferences and can be turned off. Existing saved choices
  are preserved. Weight, height, smoking, and alcohol details can be enabled
  separately for the digital page; they are off by default and never appear on
  the printable card. Up to three emergency contacts can be saved. Anyone
  possessing the QR code or link can view shared fields. Saving sharing
  preferences rotates the token and invalidates previously issued codes. Public
  card responses are not cached or indexed.
- Diary pages and their tasks are persisted per account. A page must have saved
  content or a task before the next page can be created. Completed tasks leave
  the home checklist but remain marked as completed on their original diary
  page. The separate health overview remains a UI prototype; only health data
  entered in the profile is persisted.
- Sensitive models are not exposed in Django admin. Uploaded profile images
  are validated and kept under a private media directory; public media serving
  is intentionally not configured.

## Database

PostgreSQL is the default database for local development and deployment. Install
PostgreSQL, create a dedicated database and least-privilege application role,
and configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and
`DB_SSLMODE` in the ignored `.env` file before running migrations. The example
uses loopback and `DB_SSLMODE=disable` for local development only; use
`verify-full` with a trusted certificate for remote database connections.

Install all database drivers with `python -m pip install -r requirements.txt`.
SQLite remains available by setting `DB_ENGINE=sqlite` for isolated tests or
temporary local use, but the SQLite file is not encrypted. Do not use it or
unencrypted backups to store real health data.

## Security notes

- Django's password hashers, built-in password reset tokens, CSRF middleware,
  server-side sessions, generic login/reset responses, and same-origin checks
  protect the current account flows.
- Production settings default to `DEBUG=False`, HTTPS redirects, secure
  session/CSRF cookies, and HSTS. Set exact hosts and CSRF origins. If TLS ends
  at a reverse proxy, only enable `TRUST_X_FORWARDED_PROTO` when that proxy
  removes client-supplied forwarded headers.
- A shared login rate limit, deployment secret manager, encrypted database and
  backup storage, and operational monitoring must be configured before public
  production use. No shared cache or hosting platform has been selected here.
- SOS QR cards are bearer links rather than identity-verified access. Treat
  downloaded or printed cards as public; regenerate the code to revoke prior
  online links. A downloaded copy of the card cannot be remotely revoked.
- Google sign-in is not implemented. The swappable UUID user model keeps a
  future authentication integration possible without adding provider-specific
  account state now.
- As of 2026-10-11, Django 6.1 officially lists Python 3.12-3.14 support, not
  Python 3.15. The current test suite runs in the supplied Python 3.15
  environment, but that combination is not an officially supported Django
  runtime. See the
  [Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/).

## Validation

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test SafeSpace
```
