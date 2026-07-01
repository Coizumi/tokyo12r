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

Optional GitHub Actions dispatch is controlled by:

```bash
sudoedit /etc/tokyo12r-feature-pipeline.env
```

Set `TOKYO12R_DISPATCH_WORKFLOW=1` and `GITHUB_TOKEN` only when the VPS batch
should trigger the Cloudflare Pages deploy workflow after a successful run.

Check status:

```bash
systemctl list-timers tokyo12r-feature-update.timer
journalctl -u tokyo12r-feature-update.service -n 100 --no-pager
```

Run once manually:

```bash
sudo systemctl start tokyo12r-feature-update.service
```

The service runs `scripts/jra_oci_batch.py`, which fetches official JRA race
cards, generates `site-dist`, writes private runner data to
`/opt/tokyo12r/var/oci-data.json`, ingests it into SQLite, and exports
`site-dist/features-jra.json`.
