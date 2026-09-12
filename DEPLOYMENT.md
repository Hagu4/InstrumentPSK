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
