# TOKYO12R Public Site

This site is generated for JRA race forecasting at `tokyo12r.byzin.win`.

Accuracy and publishing policy:

- Do not publish invented race, horse, odds, or result data.
- Use official JRA race-card HTML as the source for internal race and horse data.
- Publish only prediction marks, horse names, and betting formulas.
- Do not publish the full race card, horse-number table, jockey table, or past-performance table.

Generate an empty/preparation page:

```bash
python3 scripts/jra_site_updater.py --output site-dist
```

Generate from official JRA race-card HTML:

```bash
python3 scripts/jra_site_updater.py --output site-dist --date 2026-06-27 --fetch-official
```

Regenerate from a sanitized public JSON file:

```bash
python3 scripts/jra_site_updater.py --output site-dist --input site-dist/public-dataYYYYMMDD.json
```
