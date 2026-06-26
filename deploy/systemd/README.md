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

Check status:

```bash
systemctl list-timers tokyo12r-feature-update.timer
journalctl -u tokyo12r-feature-update.service -n 100 --no-pager
```

Run once manually:

```bash
sudo systemctl start tokyo12r-feature-update.service
```
