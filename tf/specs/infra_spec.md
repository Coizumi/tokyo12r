# 🏇 地方競馬予測システム インフラ構成仕様書 (v1.0)

## 1. プロジェクト概要

本プロジェクトは、地方競馬（特に園田・浦和）のデータを自動収集・解析し、機械学習モデルによる予測および買い目の提示を完全自動で行うためのインフラ環境を構築する。

* **基本方針:** OCI Always Freeリソースの最大活用
* **管理手法:** Terragrant / Terraform による構成管理 (IaC)
* **構築環境:** WSL (AlmaLinux 9)

## 2. リージョン・基本情報

* **ホームリージョン:** 東京 (ap-tokyo-1)
* **コンパートメント:** `HorseRacing_Project` (または既存の任意のもの)
* **認証方式:** APIキー認証 (`~/.oci/config`)

## 3. ネットワーク構成 (Network)

VCN（仮想クラウド・ネットワーク）を新規作成し、外部からのメンテナンス用アクセスおよびn8nのWEB UIへのアクセスを許可する。

| リソース名 | 設定値 | 備考 |
| :--- | :--- | :--- |
| **VCN CIDR** | 10.0.0.0/16 | `horse-racing-vcn` |
| **サブネット** | 10.0.1.0/24 (Public) | インターネットゲートウェイ経由 |
| **セキュリティ・リスト** | TCP: 22 (SSH) | 運用管理用 |
| | TCP: 5678 (n8n) | ワークフロー管理UI用 |
| | TCP: 80/443 | 必要に応じて（API公開用等） |
| | TCP: 1521/1522 | ADB接続用（後述） |

## 4. コンピューティング構成 (Compute)

予測エンジンの心臓部として、高スペックなARMインスタンスを利用する。

| 項目 | 設定値 | 備考 |
| :--- | :--- | :--- |
| **インスタンス名** | `horse-racing-engine` | |
| **シェイプ** | VM.Standard.A1.Flex | Always Free (ARM) |
| **リソース割当** | 4 OCPU / 24 GB RAM | 最大スペックを推奨 |
| **OSイメージ** | Oracle Linux 8 (aarch64) | または Ubuntu 22.04 |
| **ブート・ボリューム** | 50 GB ~ 100 GB | Always Free合計200GBまで |
| **パブリックIP** | 有効 | 予約済みパブリックIPの使用を推奨 |

## 5. ストレージ・データベース構成 (Storage / DB)

大量の過去データや機械学習モデルの管理に使用する。

1. **Autonomous Database (ADB):**
    * タイプ: Data Warehouse または Transaction Processing (Always Free)
    * 用途: 園田・浦和のレース結果、血統データ、指数履歴の蓄積
2. **Object Storage:**
    * 用途: 学習済みモデル（.pkl, .onnx等）のバックアップ、ログのアーカイブ

## 6. ソフトウェア・スタック (Server Software)

インスタンス内で稼働させる主要コンポーネント。

* **Docker / Docker Compose:** アプリケーションのコンテナ管理
* **n8n:** データ収集（スクレイピング）および通知ワークフローの自動実行
* **Python 3.11+:** 予測ロジック（LightGBM, Pandas, Scikit-learn等）
* **OCI CLI:** インフラ操作およびObject Storage連携用

## 7. IaC 管理構造 (Terragrunt)

WSL上のプロジェクトディレクトリ構成案。

```text
oci-project/
├── terragrant.hcl          # 共通変数 (Region, Tenancy, Compartment)
├── vpc/
│   └── terragrant.hcl      # ネットワークリソース定義
└── compute/
    └── terragrant.hcl      # インスタンス、ディスク定義 (vpcに依存)
```

## 8. セキュリティ・メンテナンス

* **認証:** 公開鍵認証 (ED25519) によるSSH接続
* **バックアップ:** ブート・ボリュームの自動バックアップ・ポリシーの適用
* **監視:** OCI Monitoring によるインスタンス生存監視（アラート通知）

---

