# TOKYO12R VPS systemd units

These units run the WebARENA Indigo VPS-side JRA feature pipeline.
Cloudflare Pages direct deploy requires Node.js 22 or newer because Wrangler
4.x requires it.

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

Cloudflare R2 archive is controlled by the same env file. Set
`TOKYO12R_R2_ARCHIVE=1` to upload the generated public JSON to R2 on each run.
The upload overwrites the same daily key, so only the final JSON for each date
is retained.

Optional R2 bucket override:

```bash
TOKYO12R_R2_BUCKET=byzin-nar-results
```

Archive keys:

```text
jra/daily/YYYY/MM/DD/public-dataYYYYMMDD.json
jra/latest/public-data.json
```

R2 upload failures are retried and then logged as non-blocking warnings. A
temporary R2 failure should not prevent the Cloudflare Pages deployment from
continuing.

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

From the Windows workstation, the same VPS-side update can be triggered with
the manual deploy helper:

```cmd
deploy\jra_deploy.cmd
```

The helper creates a temporary ACL-restricted SSH key copy, runs `git pull
--ff-only` on `/opt/tokyo12r`, starts `tokyo12r-feature-update.service`, checks
the service result, verifies the public page, and then removes the temporary
key. Secrets remain outside the repository.

Schedule:

- Fri 22:10 JST
- Sat 08:33, 12:33, 15:12, 15:57, 17:33, 22:10 JST
- Sun 08:33, 12:33, 15:12, 15:57, 17:33 JST
- Mon/Tue 08:33, 12:33, 15:12, 15:57, 17:33 JST

Fri 22:10 and Sat 22:10 prepare the next day's race card. These slots scan up
to four days from the resolved target date so the next available JRA racing day
can be generated and deployed.

On Monday and Tuesday, the first no-race check writes
`/opt/tokyo12r/var/no-race-YYYY-MM-DD.marker` when no JRA races are found.
Subsequent slots for the same day exit successfully without doing the full
pipeline unless `--ignore-no-race-marker` is supplied.

The service runs `scripts/jra_oci_batch.py`, which fetches official JRA race
cards, generates `site-dist`, writes private runner data to
`/opt/tokyo12r/var/oci-data.json`, ingests it into SQLite, and exports
`site-dist/features-jra.json`. When `TOKYO12R_R2_ARCHIVE=1`, it also archives
the public `site-dist/public-dataYYYYMMDD.json` to Cloudflare R2.
