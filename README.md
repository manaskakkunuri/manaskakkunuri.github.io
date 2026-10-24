# ULTRON — Study Smarter

A responsive student-learning frontend with a FastAPI backend foundation.

## Repository layout
- `index.html` — GitHub Pages frontend.
- `backend/main.py` — API, authentication, school portals, tasks/XP, and fail-closed manual UPI review endpoints.
- `backend/features.py` — first-successful-response AI race, subscriptions, Gemini image generation, restricted admin APIs.
- `ultron-enhancements.css` / `ultron-enhancements.js` — premium dark responsive UI, mobile navigation, Plans, Image Studio, and Super Admin Center.
- `requirements.txt` — Python dependencies.
- `.env.example` — environment variable template; never put real secrets here.

## Run the API locally
Use Python 3.11+.

1. Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, then set a real secret. Generate one with:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
4. Export the values from `.env` into your shell (or use your preferred environment loader). Do not commit `.env`.
5. Run `uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload`.
6. Visit `http://127.0.0.1:8000/docs`.

The frontend reads its API base URL from the `ultron-api-base-url` meta tag near the top of `index.html`. Set it to the HTTPS URL of the deployed API before using account login or registration. Configure the API's `ALLOWED_ORIGINS` to the exact frontend origin. GitHub Pages hosts static files only; it does not run FastAPI.

## AI, subscriptions, and image studio
- `/ai/answer` races TinyFish live web search and Google Gemini text generation concurrently; the first usable successful result wins, and failed providers are skipped. TinyFish returns live source links/snippets; Gemini returns a tutor response. The API reports provider and elapsed time.
- Configure `TINYFISH_API_KEY`, `GEMINI_API_KEY`, `TINYFISH_SEARCH_URL`, `GEMINI_TEXT_MODEL`, and `GEMINI_IMAGE_MODEL` as backend environment variables only. Never put keys in HTML, JavaScript, or Git. Rotate any key shared in chat.
- `/images/generate` uses Gemini image generation. Free: 20 AI requests/day and 2 images/month; Basic ₹99/month: 250/day and 15 images/month; Pro ₹299/month: 1,000/day and 60 images/month. Server-side quotas apply; provider billing and rate limits still apply.
- `/subscriptions/me` reports plan and usage; `/subscriptions/upi-claims` accepts a claim but never activates a subscription by UTR alone. A trusted operations process must call `/ops/payments/{claim_id}/verify` with `X-Payment-Reconciliation-Secret`; an authorized reviewer then approves via `/admin/subscriptions/{claim_id}/approve`. Approved plans last 30 days.
- Super Admin UI requires a verified account, a separately provisioned `super_admin` role, and the two-email allowlist. Allowlisting alone never grants privileges.

## API notes
- Registration requires a 12-character password and creates an unverified student account. A real email-verification workflow is intentionally not faked and must be implemented before verified-only features can be used.
- Roles are never granted by email address. Provision school-admin and super-admin roles through a trusted, audited operations process—not a public API endpoint.
- UTR is validated as exactly 12 digits, but is not proof of payment. Manual UPI approval is locked until an independent bank/provider reconciliation process is implemented. Subscriptions activate only after trusted payment reconciliation and authorized reviewer approval; a UTR alone never activates a plan.
- The two permitted manual UPI reviewers are `ashokbharadwaj@gmail.com` and `manaskakkunuri55@gmail.com`; both still need a verified email and separately provisioned `super_admin` role.
- XP is awarded once when a task transitions from incomplete to complete.
- Database tables are created for local development; use migrations and PostgreSQL for production.

## Important limitations
This is a foundation, not a production-complete service. Add rate limiting, verification and reset emails, robust migrations, automated security/integration tests, real-time chat transport, secure file uploads, subscription lifecycle logic, and deployment monitoring before launch.


## Presentation demo and backend deployment
- The login page includes **Explore presentation demo** for a clearly labelled, local-only walkthrough. It does not authenticate a user, create an account, or unlock real AI, billing, image generation, or admin actions. The tutor's sample answer is explicitly marked as sample content.
- A Render deployment blueprint is available in `render.yaml`. In Render, create a Blueprint from this repository and configure the required secret values in Render's environment settings; never commit provider keys.
- After Render creates the API, set the `ultron-api-base-url` meta tag in `index.html` to the exact HTTPS service URL, then confirm `/health` returns `{"status":"ok","service":"ultron-api"}`. The configured CORS origin must match the GitHub Pages origin exactly.
- The included SQLite URL is only a quick-start configuration. SQLite on an ephemeral free service is not durable production storage; configure managed PostgreSQL and backups before real accounts, payment claims, or school use. A Render service and provider secrets must be provisioned by an account owner before live backend functionality can work.
