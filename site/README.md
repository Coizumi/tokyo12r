# TOKYO12R public site

This site is generated for JRA race forecasting.

Accuracy policy:

- Do not publish invented race, horse, odds, or result data.
- Show `開催無し` when no official race data has been loaded for the target date.
- Use official JRA announcements as the source for race and horse data.

Generation:

```bash
python3 scripts/jra_site_updater.py --output site-dist
```

When official race data is available as JSON:

```bash
python3 scripts/jra_site_updater.py --output site-dist --input site/public-dataYYYYMMDD.json
```
