# SEP Tracker skill (OpenClaw Igor)

Target the **public Agent Medicare Hub page**, not the old standalone Netlify site.

- Public page: https://agentmedicarehub.com/sep-tracker
- Repo: https://github.com/yperez-dot/agent-medicare-hub
- Skill/code in the repo: `sep-tracker/update_from_healthspring.py`
- Preview only: `python3 sep-tracker/preview_deploy.py`
- Production publish uses `python3 deploy_hub.py` and **must wait for Yahoska's explicit yes**. Do not enable unattended production deploys.

Do **not** run `~/.openclaw/workspace/skills/sep-tracker/deploy_to_netlify.py` against https://shimmering-figolla-ad0c9e.netlify.app. That site is the old copy. After 08.21.2026 the public page is the hub repo.

## Weekly job

Schedule: Monday 9:00 AM America/New_York, after the HealthSpring DST-SEP weekly notice.

1. Save the HealthSpring DST-SEP email body to a text file (tracking URLs can stay; the parser strips them).
2. From a checkout of `yperez-dot/agent-medicare-hub`, on a branch:
   `python3 sep-tracker/update_from_healthspring.py --email THAT_FILE --as-of TODAY --write`
3. Review the printed added/changed rows, especially Florida and Texas.
4. Draft-deploy a preview with `python3 sep-tracker/preview_deploy.py`.
5. Open or update a pull request. Tell Yahoska the PR link and preview link.
6. Stop. Do not merge and do not run `deploy_hub.py` until she says yes.

## Tokens and access (never print secrets)

- Netlify: a token that can draft-deploy site `thei-agent-hub` (site id `fba5b50f-a619-46aa-97d4-2b660a4959ca`). Prefer `NETLIFY_HUB_TOKEN` in `~/.openclaw/credentials/netlify-token.txt`, or `NETLIFY_AUTH_TOKEN_NEW` if that is the hub token.
- GitHub: the `igor-thei` token was revoked on 10.22.2026. To commit and open PRs, Igor needs a new fine-grained token with `contents:write` and `pull-requests:write` on `yperez-dot/agent-medicare-hub` only, stored in OpenClaw credentials (not in chat, not in the repo).
- Mailbox: access to whichever inbox receives the HealthSpring ARC / DST-SEP weekly email, so the Monday job can pick up the notice without waiting for a manual paste.

If a token or mailbox is missing, say so and stop. Do not reuse Railway Igor; those services staying down is expected.
