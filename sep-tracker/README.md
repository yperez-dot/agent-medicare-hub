# SEP tracker tools

The only tracker page to edit is [`pages/sep-tracker-app.html`](../pages/sep-tracker-app.html). That is the file https://agentmedicarehub.com/sep-tracker and the Spanish shell load (via `pages/sep-tracker.html` and `pages/es/sep-tracker.html`).

Do not add another HTML copy of the tracker. The old standalone `sep-tracker/index.html` was removed so weekly updates cannot drift from the public page.

- `update_from_healthspring.py` writes embedded `DATA` into `pages/sep-tracker-app.html`
- `validate_embedded_data.py` checks that public file before deploy
