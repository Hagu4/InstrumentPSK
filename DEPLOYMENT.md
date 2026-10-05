# Production deployment

The production branch is `release/production`. Build and deploy only a clean commit
from this repository. The original master checkout contains unfinished work and
must not be uploaded wholesale.

Use `git archive --format=tar -o release.tar HEAD`. This contains tracked source only;
never archive the working directory. Keep artifacts outside the checkout.

Runtime files on the server, excluded from Git and Docker build context:

- `DjangoWebProject1/.env`: Django, SMTP and DATABASE_URL (mode 600).
- `DjangoWebProject1/.env.db`: POSTGRES_DB/USER/PASSWORD (mode 600).
- Media, PostgreSQL volumes and TLS certificates must survive deployment.

The web service forces DEBUG=False and is only reachable through nginx. PostgreSQL
has no published host port. Do not use `docker compose down -v`.

Release steps: backup database, build image, run Django deployment checks,
apply reviewed migrations, run collectstatic, restart web, reload nginx, check HTTPS.
Changing POSTGRES_PASSWORD alone does not rotate a persisted database role.
Coordinate ALTER ROLE with DATABASE_URL and web restart. Never roll back to exposed keys.

HSTS initially uses 3600 seconds without includeSubDomains/preload. Increase only after
confirming HTTPS for all relevant hosts. The corresponding Django deployment warnings
are intentional during this rollout.

Password reset delivery errors produce the same response as unknown accounts.
Monitor `app.password_reset` errors in container logs. SMTP error bodies and recipients
are deliberately omitted. An SMTP outage requires operator attention; no background
retry queue is introduced by this patch.

## Private error journal

Migration `app.0044_error_journal` adds a metadata-only journal at
`/admin/app/errorevent/`. Only active superusers can view it or mark entries
resolved. Staff permissions do not grant access; adding/deleting entries through
the admin is disabled.

The `got_request_exception` receiver captures new unhandled Django request
exceptions. It records the URL pattern (not actual parameter values), method,
exception class and up to 40 file/function/line frames. Exception messages,
source code, locals, request bodies, headers, query strings and user identities
are deliberately excluded. A stack identifies where the error occurred but does
not always explain its full cause without further investigation.

Repeated signatures increment a counter and reopen resolved entries. On each
successful write entries inactive for 30 days are removed, and the newest 1000
signatures are retained. This is write-triggered retention, not a scheduled purge.
Database write failure emits only the exception class to the fallback logger;
it does not replace the original exception. It cannot record an unavailable
server or deliberately returned/caught HTTP 500 responses. Keep infrastructure
monitoring and container logs as a separate source of evidence.

Deploy the migration before restarting web workers. Do not add a public crash
endpoint for verification. Use automated tests and an isolated internal check.
