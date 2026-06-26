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

- fetch and normalize JRA data
- store features, predictions, results, payouts, and outcomes in SQLite
- generate weekly, monthly, and yearly performance summaries
- export lightweight JSON artifacts for the static site pipeline

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
