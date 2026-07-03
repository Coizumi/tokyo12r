# TOKYO12R VPS systemd units

These units run the WebARENA Indigo VPS-side JRA feature pipeline.

Assumed deployment directory:

```bash
/opt/tokyo12r
```

Install on the VPS:

```bash
sudo timedatectl set-timezone Asia/Tokyo
sudo useradd --system --create-home --shell /usr/sbin/nologin tokyo12r || true
sudo chown -R tokyo12r:tokyo12r /opt/tokyo12r
sudo cp deploy/systemd/tokyo12r-feature-update.service /etc/systemd/system/
sudo cp deploy/systemd/tokyo12r-feature-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tokyo12r-feature-update.timer
```

Cloudflare Pages direct deploy is controlled by:

```bash
sudoedit /etc/tokyo12r-feature-pipeline.env
```

Set `CLOUDFLARE_PAGES_DEPLOY=1`, `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT_NAME=tokyo12r`, and
`CLOUDFLARE_PAGES_BRANCH=main` so the VPS batch deploys `site-dist` directly
to Cloudflare Pages after a successful run.

GitHub Actions dispatch remains available as a backup path. Set
`TOKYO12R_DISPATCH_WORKFLOW=1` and `GITHUB_TOKEN` only when the VPS batch
should also trigger the Cloudflare Pages deploy workflow.

Check status:

```bash
systemctl list-timers tokyo12r-feature-update.timer
journalctl -u tokyo12r-feature-update.service -n 100 --no-pager
```

Run once manually:

```bash
sudo systemctl start tokyo12r-feature-update.service
```

Schedule:

- Fri 22:10 JST
- Sat/Sun 08:33, 12:33, 15:12, 15:57, 17:33 JST
- Mon/Tue 08:33, 12:33, 15:12, 15:57, 17:33 JST

On Monday and Tuesday, the first no-race check writes
`/opt/tokyo12r/var/no-race-YYYY-MM-DD.marker` when no JRA races are found.
Subsequent slots for the same day exit successfully without doing the full
pipeline unless `--ignore-no-race-marker` is supplied.

The service runs `scripts/jra_oci_batch.py`, which fetches official JRA race
cards, generates `site-dist`, writes private runner data to
`/opt/tokyo12r/var/oci-data.json`, ingests it into SQLite, and exports
`site-dist/features-jra.json`.
