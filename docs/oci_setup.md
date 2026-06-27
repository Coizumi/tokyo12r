# JRA OCI Setup

This document records the intended OCI placement for the JRA site.

## Target

- Site: TOKYO12R by ZIN
- Repository: `https://github.com/Coizumi/tokyo12r.git`
- Region: `ap-tokyo-1`
- Compartment OCID: `ocid1.compartment.oc1..aaaaaaaaavsn2rim6u3ka66526ggdbkd2gvxi26woaz2oau7gugvkep6vg4a`

## Status

Terraform configuration has been added under `tf/`.

The OCI VM is intended to run only the backend batch:

- fetch current or next available JRA race cards from the official JRA HTML
- generate the public `site-dist` HTML/JSON artifacts locally
- store features, predictions, results, payouts, and outcomes in SQLite
- store published picks and generated bet tickets from `public-dataYYYYMMDD.json`
- generate weekly, monthly, and yearly performance summaries
- export lightweight JSON artifacts for the static site pipeline
- optionally dispatch the GitHub Actions deploy workflow

The public site remains on Cloudflare Pages. The OCI VM does not need inbound
HTTP/HTTPS access; only SSH from the administrator CIDR is opened.

## Terraform

Copy `tf/terraform.tfvars.example` to `tf/local.auto.tfvars` and set:

- `tenancy_ocid`
- `user_ocid`
- `fingerprint`
- `private_key_path`
- `admin_cidr`
- `ssh_public_key_path`

Then run:

```bash
cd tf
terraform init
terraform plan
terraform apply
```

Default compute shape:

- `VM.Standard.A1.Flex`
- `1` OCPU
- `6` GiB memory
- `50` GiB boot volume

This is enough for SQLite, scheduled scraping, feature generation, and summary
aggregation. Increase only if historical backfill becomes slow.

## Runtime

Cloud-init installs the systemd units and enables:

```bash
tokyo12r-feature-update.timer
tokyo12r-feature-update.service
```

The service runs:

```bash
python3 /opt/tokyo12r/scripts/jra_oci_batch.py
```

One batch execution performs:

1. `git pull --ff-only` in `/opt/tokyo12r`
2. `jra_site_updater.py --fetch-official` to generate `site-dist`
3. write private OCI data to `/opt/tokyo12r/var/oci-data.json`
4. `jra_feature_pipeline.py --public-data ...` to ingest runners, bloodline fields, predictions, and tickets into SQLite
5. export `/opt/tokyo12r/site-dist/features-jra.json`
6. optionally call GitHub `workflow_dispatch`

Runtime paths:

- SQLite: `/opt/tokyo12r/var/jra_features.sqlite3`
- Private OCI ingest JSON: `/opt/tokyo12r/var/oci-data.json`
- Public site artifacts: `/opt/tokyo12r/site-dist/`
- Feature JSON: `/opt/tokyo12r/site-dist/features-jra.json`
- Environment file: `/etc/tokyo12r-feature-pipeline.env`

Check the timer and recent logs:

```bash
systemctl list-timers tokyo12r-feature-update.timer
journalctl -u tokyo12r-feature-update.service -n 100 --no-pager
```

Run once manually:

```bash
sudo systemctl start tokyo12r-feature-update.service
```

To make OCI trigger the Cloudflare Pages deployment workflow after a successful
batch, set these values on the VM:

```bash
sudoedit /etc/tokyo12r-feature-pipeline.env
```

```text
TOKYO12R_DISPATCH_WORKFLOW=1
GITHUB_REPOSITORY=Coizumi/tokyo12r
GITHUB_WORKFLOW=deploy-tokyo12r.yml
GITHUB_TOKEN=github_pat_or_fine_grained_token
```

The token needs permission to dispatch Actions workflows for the repository.
