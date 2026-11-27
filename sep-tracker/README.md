# SEP Tracker

Public page: https://agentmedicarehub.com/sep-tracker

The live table is the `var DATA` array inside `pages/sep-tracker-app.html`. `data/seps.json` is the disaster-SEP catalog used to rebuild that array. Year-round Dual/LIS rows live in `data/yearround.json` so they are not dropped on refresh.

## Update from a HealthSpring DST-SEP notice

This writes local files only. It does not merge, and it does not deploy to production.

```bash
python3 sep-tracker/update_from_healthspring.py \
  --email path/to/healthspring-notice.txt \
  --as-of YYYY-MM-DD \
  --write
```

To rebuild from Igor's standalone 10.21.2026 snapshot and then apply a notice (the 11.27.2026 refresh):

```bash
python3 sep-tracker/update_from_healthspring.py \
  --replace-json sep-tracker/data/source_2026-10-21.json \
  --email sep-tracker/data/healthspring-2026-11-27.txt \
  --as-of 2026-11-27 \
  --keep-hub-unique \
  --write
```

`--keep-hub-unique` keeps disaster rows that were on the public page but missing from the snapshot (for example later FEMA fire listings), after skipping duplicates.

Then open a preview (never production):

```bash
python3 sep-tracker/preview_deploy.py
```

Do not run `deploy_hub.py` (production) until Yahoska explicitly says to publish.

## Dates

Use MM.DD.YYYY in the hero chip and in chat. Status is recomputed from `--as-of` (active / ending soon / ended). Ending soon is 30 days or fewer remaining.
