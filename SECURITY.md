# Security policy

## Reporting
Do not publish credentials, payment identifiers, or exploitable vulnerabilities in public issues. Contact the repository owner privately and include a reproducible description.

## Current security boundaries
- The frontend is a static GitHub Pages site; authentication must be provided by the separately deployed API.
- The API requires a strong `SECRET_KEY` and never persists passwords or access tokens in browser localStorage.
- Public registration always creates an unverified student. There is no public endpoint to promote users, verify email, or mark a UPI payment as independently verified.
- Manual UPI review requires both the fixed reviewer email allowlist and a separately provisioned, verified `super_admin` database role. Email allowlisting alone grants no role.
- Payment approval fails closed unless an independent reconciliation process has verified the payment. Approval does not activate a subscription.

## Before production
Implement real email verification and password reset, rate limiting, database migrations/backups, monitoring, HTTPS, restrictive CORS, security tests, and a trusted payment reconciliation workflow. Use PostgreSQL in production. Never store production secrets in Git.
