# TOKYO12R WebARENA Indigo Introduction

## 採用サービス

TOKYO12R のJRA特徴量パイプラインは、WebARENA Indigo の 2GB Linux VPS を標準実行環境とする。

```text
service: WebARENA Indigo Linux
plan: 2GB
cpu: 2vCPU
memory: 2GB
ssd: 40GB
network: 100Mbps upper limit
region: Tokyo
monthly upper limit: 814 JPY
```

採用理由:

- TOKYO12R の用途では常時公開Webサーバーではなく、systemd timerで動く小型バッチが中心
- 2GBメモリがあれば、Git、Python、SQLite、JRA取得処理の同時実行に現実的な余裕がある
- Cloudflare Pages は継続利用し、VPSは永続DBとバッチ処理だけに限定できる
- OCI無料利用枠で発生した容量不足や低スペックVMの詰まりを避けられる

公式ページ:

- WebARENA Indigo: https://web.arena.ne.jp/indigo/
- Indigo スタートアップガイド: https://help.arena.ne.jp/hc/ja/articles/360049817054

## 契約前に用意するもの

- 契約者情報
- 受信できるメールアドレス
- SMSまたは電話認証を受けられる電話番号
- クレジットカード
- SSH公開鍵

SSH鍵はローカルPCで作成しておく。

```powershell
ssh-keygen -t ed25519 -f D:\dev\jra\xtra\webarena_indigo_id_ed25519 -C tokyo12r-webarena
```

```powershell
ssh-keygen -t rsa -f D:\dev\jra\xtra\webarena_indigo_id_rsa -C tokyo12r-webarena-rsa
```

公開鍵は以下のファイルを使う。

```text
D:\dev\jra\xtra\webarena_indigo_id_ed25519.pub
```

```text
D:\dev\jra\xtra\webarena_indigo_id_rsa.pub
```

秘密鍵は外部に貼り付けない。

## 契約手順

1. WebARENA Indigo の公式ページを開く
2. 「お申し込み」または申込導線からアカウント登録へ進む
3. メールアドレスを登録し、確認メールのリンクで認証する
4. 契約者情報を入力する
5. SMS認証または電話認証を完了する
6. クレジットカードを登録する
7. Indigo の管理画面へログインする

この時点では、まだインスタンスを作成しない。SSH公開鍵とOS選定を確認してから作成する。

## インスタンス作成手順

1. Indigo 管理画面でインスタンス作成を選ぶ
2. サービスは Linux を選ぶ
3. リージョンは Tokyo を選ぶ
4. プランは 2GB を選ぶ
5. OSは Ubuntu 24.04 LTS または AlmaLinux 9 を選ぶ
6. SSH公開鍵に `webarena_indigo_id_ed25519.pub` の内容を登録する
7. インスタンス名は `tokyo12r-batch-01` とする
8. 作成内容を確認してインスタンスを作成する
9. グローバルIPアドレスを控える

OSは運用の簡単さを優先するなら Ubuntu 24.04 LTS、既存のAlmaLinux操作感を優先するなら AlmaLinux 9 とする。迷う場合は Ubuntu 24.04 LTS を選ぶ。

## 初回SSH接続

インスタンス作成後、管理画面で表示されたグローバルIPへ接続する。

Ubuntuの場合:

```powershell
ssh -i D:\dev\jra\xtra\webarena_indigo_id_ed25519 ubuntu@<PUBLIC_IP>
```

```powershell
ssh -i D:\dev\jra\xtra\webarena_indigo_id_rsa ubuntu@161.34.66.248
```

AlmaLinuxの場合:

```powershell
ssh -i D:\dev\jra\xtra\webarena_indigo_id_ed25519 almalinux@<PUBLIC_IP>
```

接続できたら、作業用ユーザーとOSを確認する。

```bash
whoami
cat /etc/os-release
timedatectl
```

```bash
ubuntu@i-53100000788730:~$ whoami
ubuntu
ubuntu@i-53100000788730:~$ cat /etc/os-release
timedatectl
PRETTY_NAME="Ubuntu 24.04 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
LOGO=ubuntu-logo
               Local time: Wed 2026-07-01 01:40:14 UTC
           Universal time: Wed 2026-07-01 01:40:14 UTC
                 RTC time: Wed 2026-07-01 01:40:14
                Time zone: Etc/UTC (UTC, +0000)
System clock synchronized: no
              NTP service: active
          RTC in local TZ: no
ubuntu@i-53100000788730:~$
```

## 初期設定

timezoneをJSTに設定する。

```bash
sudo timedatectl set-timezone Asia/Tokyo
```

```bash
ubuntu@i-53100000788730:~$ timedatectl
               Local time: Wed 2026-07-01 10:41:16 JST
           Universal time: Wed 2026-07-01 01:41:16 UTC
                 RTC time: Wed 2026-07-01 01:41:16
                Time zone: Asia/Tokyo (JST, +0900)
System clock synchronized: no
              NTP service: active
          RTC in local TZ: no
```

Ubuntuの場合:

```bash
sudo apt update
sudo apt -y upgrade
sudo apt -y install git python3 python3-pip python3-venv python3-bs4 sqlite3 curl
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt -y install nodejs
```

Cloudflare Wrangler最新版はNode.js 22以上を要求するため、Ubuntu標準リポジトリのNode.js 18ではなくNodeSourceのNode.js 22を利用する。

```bash
ubuntu@i-53100000788730:~$ sudo apt -y install git python3 python3-pip python3-venv python3-bs4 sqlite3 curl
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
git is already the newest version (1:2.43.0-1ubuntu7.3).
python3 is already the newest version (3.12.3-0ubuntu2.1).
python3-pip is already the newest version (24.0+dfsg-1ubuntu1.3).
python3-venv is already the newest version (3.12.3-0ubuntu2.1).
python3-bs4 is already the newest version (4.12.3-1).
sqlite3 is already the newest version (3.45.1-1ubuntu2.6).
curl is already the newest version (8.5.0-2ubuntu10.9).
The following packages were automatically installed and are no longer required:
  libfwupd2 libgusb2
Use 'sudo apt autoremove' to remove them.
0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
ubuntu@i-53100000788730:~$
```

AlmaLinuxの場合:

```bash
sudo dnf -y update
sudo dnf -y install git python3 python3-pip python3-beautifulsoup4 sqlite curl
```

## ファイアウォール方針

VPSはWeb公開しないため、外部公開はSSHのみとする。

- SSH: 管理元IPからのみ許可
- HTTP/HTTPS: 原則不要
- JRA取得とGitHub/Cloudflare連携: outboundのみ利用

WebARENA管理画面またはOS側ファイアウォールで、可能ならSSHの接続元を自宅/作業場所IPに限定する。

UbuntuでOS側も制限する例:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <ADMIN_CIDR> to any port 22 proto tcp
sudo ufw enable
```

## TOKYO12R配置 --- Codex作業

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin tokyo12r || true
sudo mkdir -p /opt
sudo install -d -o tokyo12r -g tokyo12r /opt/tokyo12r
sudo -u tokyo12r git clone https://github.com/Coizumi/tokyo12r.git /opt/tokyo12r
sudo -u tokyo12r mkdir -p /opt/tokyo12r/var /opt/tokyo12r/logs
```

実施結果:

```text
配置先: /opt/tokyo12r
実行ユーザー: tokyo12r
取得commit: c7a69e7
```

Python構文チェック:

```bash
cd /opt/tokyo12r
sudo -u tokyo12r python3 -m py_compile scripts/jra_site_updater.py scripts/jra_feature_pipeline.py scripts/jra_oci_batch.py
```

実施結果: 成功。

## systemd timer設定

既存のsystemd unitを配置する。

```bash
sudo cp /opt/tokyo12r/deploy/systemd/tokyo12r-feature-update.service /etc/systemd/system/
sudo cp /opt/tokyo12r/deploy/systemd/tokyo12r-feature-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tokyo12r-feature-update.timer
```

systemd serviceは、Ubuntu/AlmaLinux差を避けるため専用ユーザー `tokyo12r` で実行する。

動作確認:

```bash
systemctl list-timers tokyo12r-feature-update.timer
sudo systemctl start tokyo12r-feature-update.service
sudo journalctl -u tokyo12r-feature-update.service -n 100 --no-pager
```

実施結果:

```text
timer enabled: enabled
timer active: active
next run: Fri 2026-07-03 22:00:00 JST
manual service run: status=0/SUCCESS
```

`2026-07-01` 起点の手動service実行ではJRA開催が取得できず、0レース生成となった。
パイプラインの実データ検証として、直近開催日の `2026-06-28` を指定して手動実行した。

```bash
sudo -u tokyo12r /usr/bin/python3 /opt/tokyo12r/scripts/jra_oci_batch.py \
  --repo-dir /opt/tokyo12r \
  --output /opt/tokyo12r/site-dist \
  --db /opt/tokyo12r/var/jra_features.sqlite3 \
  --sire-data /opt/tokyo12r/data/Sire_data.csv \
  --public-output /opt/tokyo12r/site-dist/features-jra.json \
  --date 2026-06-28 \
  --skip-pull
```

実施結果:

```text
Generated 36 races into /opt/tokyo12r/site-dist
Imported 100 sires, 36 races, 180 predictions, 1044 tickets, wrote 459 runner features and 0 summaries.
GitHub workflow dispatch is disabled.

/opt/tokyo12r/var/jra_features.sqlite3: 516K
/opt/tokyo12r/var/oci-data.json: 327K
/opt/tokyo12r/site-dist/features-jra.json: 93K
```

SQLite件数確認:

```text
races: 36
predictions: 180
runner_features: 459
performance_summaries: 0
```

## Cloudflare Pages直接デプロイ

標準運用では、VPSからCloudflare Pagesへ直接デプロイする。
GitHub Actionsは手動再生成、緊急時、検証用のバックアップ経路として残す。

VPSからCloudflare Pagesへ直接デプロイする場合は、環境ファイルを作成する。

```bash
sudo install -m 600 -o root -g root /dev/null /etc/tokyo12r-feature-pipeline.env
sudoedit /etc/tokyo12r-feature-pipeline.env
```

設定例:

```text
CLOUDFLARE_PAGES_DEPLOY=1
CLOUDFLARE_API_TOKEN=<cloudflare-api-token>
CLOUDFLARE_ACCOUNT_ID=<cloudflare-account-id>
CLOUDFLARE_PAGES_PROJECT_NAME=tokyo12r
CLOUDFLARE_PAGES_BRANCH=main
```

Cloudflare tokenは、Pagesデプロイに必要な最小限の権限で作成し、リポジトリへコミットしない。

GitHub Actions dispatchをバックアップ経路としてVPSから起動する場合のみ、同じ環境ファイルに以下を追加する。

```text
TOKYO12R_DISPATCH_WORKFLOW=1
GITHUB_REPOSITORY=Coizumi/tokyo12r
GITHUB_WORKFLOW=deploy-tokyo12r.yml
GITHUB_TOKEN=<fine-grained-or-classic-token>
```

GitHub tokenは、必要最小限の権限で作成し、リポジトリへコミットしない。

2026-07-03時点では `/etc/tokyo12r-feature-pipeline.env` にCloudflare Pages直接デプロイ設定を配置し、VPSバッチ成功後に `site-dist` をCloudflare Pagesへ反映する。

## 移行時の注意

- OCI検証VMとVCN等のTerraform管理リソースは、WebARENA運用開始前に削除する
- `scripts/jra_oci_batch.py` は現時点では既存名のまま利用できる
- 後続で `scripts/jra_vps_batch.py` にリネームする場合は、systemd unitも同時に更新する
- SQLiteは `/opt/tokyo12r/var/jra_features.sqlite3` を正とし、バックアップを定期保存する

## 完了条件

- [x] SSH接続できる
- [x] `Asia/Tokyo` が設定されている
- [x] Git/Python/SQLiteが利用できる
- [x] `/opt/tokyo12r` にリポジトリが配置されている
- [x] `python3 -m py_compile` が成功する
- [x] `tokyo12r-feature-update.timer` が有効化されている
- [x] 手動実行で `jra_features.sqlite3` と公開用JSONが生成される
- [x] Cloudflare Pages直接デプロイ用tokenを `/etc/tokyo12r-feature-pipeline.env` に設定する
