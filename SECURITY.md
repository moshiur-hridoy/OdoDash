# Security Policy

## Supported versions

Security fixes go into the latest release. OdoDash is maintained by one person,
so older versions are not patched: update to the newest image
(`ghcr.io/moshiur-hridoy/ododash:latest`) to get a fix.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it privately through GitHub:
[Report a vulnerability](https://github.com/moshiur-hridoy/OdoDash/security/advisories/new).

Include what you found, the version (shown in Settings and in the startup log),
and the steps to reproduce it. A proof of concept helps.

You can expect:

- an acknowledgement within a few days;
- an update when the problem is confirmed or ruled out;
- a fix in the next release, and a credit in the changelog if you want one.

OdoDash is maintained in spare time, so please allow reasonable time for a fix
before disclosing the problem publicly.

## Scope

In scope: the OdoDash application, its Docker image and the supplied compose
files.

Out of scope: problems in how you host it (an exposed port, a reverse proxy
without HTTPS, a weak admin password), and issues that need an already
signed-in administrator.

## Running OdoDash safely

- Set your own `SECRET_KEY` (`openssl rand -hex 32`) or let OdoDash generate one.
  Example values are ignored.
- Put OdoDash behind a reverse proxy that serves HTTPS, and set a strong
  `ADMIN_PASSWORD` or change the generated one after your first login.
- Keep the data volume backed up, and pull new images regularly.
