# TOKYO12R OCI systemd units

These units run the OCI-side JRA feature pipeline.

Assumed deployment directory:

```bash
/opt/tokyo12r
```

Install on the OCI VM:

```bash
sudo timedatectl set-timezone Asia/Tokyo
sudo cp deploy/systemd/tokyo12r-feature-update.service /etc/systemd/system/
sudo cp deploy/systemd/tokyo12r-feature-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tokyo12r-feature-update.timer
```

Optional GitHub Actions dispatch is controlled by:

```bash
sudoedit /etc/tokyo12r-feature-pipeline.env
```

Set `TOKYO12R_DISPATCH_WORKFLOW=1` and `GITHUB_TOKEN` only when the OCI batch
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
