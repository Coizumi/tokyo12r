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

公開鍵は以下のファイルを使う。

```text
D:\dev\jra\xtra\webarena_indigo_id_ed25519.pub
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

## 初期設定

timezoneをJSTに設定する。

```bash
sudo timedatectl set-timezone Asia/Tokyo
```

Ubuntuの場合:

```bash
sudo apt update
sudo apt -y upgrade
sudo apt -y install git python3 python3-pip python3-venv python3-bs4 sqlite3 curl
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

## TOKYO12R配置

```bash
sudo mkdir -p /opt/tokyo12r
sudo chown "$USER":"$USER" /opt/tokyo12r
git clone https://github.com/Coizumi/tokyo12r.git /opt/tokyo12r
mkdir -p /opt/tokyo12r/var /opt/tokyo12r/logs
```

Python構文チェック:

```bash
cd /opt/tokyo12r
python3 -m py_compile scripts/jra_site_updater.py scripts/jra_feature_pipeline.py scripts/jra_oci_batch.py
```

## systemd timer設定

既存のsystemd unitを配置する。

```bash
sudo cp /opt/tokyo12r/deploy/systemd/tokyo12r-feature-update.service /etc/systemd/system/
sudo cp /opt/tokyo12r/deploy/systemd/tokyo12r-feature-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tokyo12r-feature-update.timer
```

動作確認:

```bash
systemctl list-timers tokyo12r-feature-update.timer
sudo systemctl start tokyo12r-feature-update.service
sudo journalctl -u tokyo12r-feature-update.service -n 100 --no-pager
```

## GitHub Actions連携

VPSからGitHub Actionsを起動する場合は、環境ファイルを作成する。

```bash
sudo install -m 600 -o root -g root /dev/null /etc/tokyo12r-feature-pipeline.env
sudoedit /etc/tokyo12r-feature-pipeline.env
```

設定例:

```text
TOKYO12R_DISPATCH_WORKFLOW=1
GITHUB_REPOSITORY=Coizumi/tokyo12r
GITHUB_WORKFLOW=<workflow-file-or-id>
GITHUB_TOKEN=<fine-grained-or-classic-token>
```

GitHub tokenは、必要最小限の権限で作成し、リポジトリ外へ保存しない。

## 移行時の注意

- OCI検証VMとVCN等のTerraform管理リソースは、WebARENA運用開始前に削除する
- `scripts/jra_oci_batch.py` は現時点では既存名のまま利用できる
- 後続で `scripts/jra_vps_batch.py` にリネームする場合は、systemd unitも同時に更新する
- SQLiteは `/opt/tokyo12r/var/jra_features.sqlite3` を正とし、バックアップを定期保存する

## 完了条件

- SSH接続できる
- `Asia/Tokyo` が設定されている
- Git/Python/SQLiteが利用できる
- `/opt/tokyo12r` にリポジトリが配置されている
- `python3 -m py_compile` が成功する
- `tokyo12r-feature-update.timer` が有効化されている
- 手動実行で `jra_features.sqlite3` と公開用JSONが生成される
