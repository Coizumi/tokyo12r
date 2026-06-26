# TOKYO12R JRA Feature Pipeline Specs

## 目的

TOKYO12R by ZIN のJRA予想を、現在の軽量ヒューリスティックから、過去競走データに基づく指数型へ拡張する。

対象指数:

- 血統補正: レース条件、芝/ダートと距離に対する種牡馬適性
- 持ちタイム指数: 同条件または近似条件での走破時計評価
- 末脚指数: 上がり性能、終盤加速、差し脚の評価
- 先行力指数: 序盤位置取り、通過順、先行安定性の評価

## 基本方針

GitHub Actionsには重いデータ収集や過去データ再計算を載せない。

役割分担:

- OCI VM: データ収集、SQLite蓄積、指数計算、公開用特徴量ファイル生成
- GitHub Actions: 当日JRA出走表取得、公開HTML生成、Cloudflare Pagesデプロイ
- Cloudflare Pages: 静的サイト配信

OCI側は小さいVMを前提に、差分更新とSQLite中心で構成する。全量再取得や重い機械学習は初期対象外とする。

## 更新スケジュール

OCI VMのtimezoneを `Asia/Tokyo` に設定する。

通常更新:

- 金曜 22:00 JST
- 土曜 09:32, 10:32, ..., 17:32 JST
- 日曜 09:32, 10:32, ..., 17:32 JST
- 月曜 09:32, 10:32, ..., 17:32 JST
- 火曜 09:32, 10:32, ..., 17:32 JST

月曜・火曜は開催がある場合のみ実処理する。スケジュール自体は毎週起動し、スクリプト側で開催なしなら正常終了する。

最大実行回数は週37回程度。

## データ保存

OCI VM上のSQLiteを主ストアとする。

想定パス:

```text
/opt/tokyo12r/var/jra_features.sqlite3
```

主なテーブル:

- `sire_aptitude`: 種牡馬適性参照
- `races`: レース基本情報
- `race_entries`: 出走馬情報
- `past_performances`: 過去走
- `runner_features`: 出走馬単位の指数
- `pipeline_runs`: バッチ実行履歴

公開用には、SQLite全体ではなく軽量JSON/CSVのみを出力する。

## 血統補正

静的参照ファイル:

```text
data/Sire_data.csv
```

列:

- `sire_name`
- `surface_axis`
- `distance_m`
- `confidence`
- `source`

`surface_axis` は以下の意味を持つ。

```text
-100 = ダート寄り
0    = 中間
100  = 芝寄り
```

レース条件の目標値:

```text
芝   => 100
ダート => -100
障害 => 0
```

血統補正の初期式:

```text
surface_fit = 1 - min(abs(sire.surface_axis - race_surface_axis), 200) / 200
distance_fit = 1 - min(abs(sire.distance_m - race_distance_m), 600) / 600
sire_fit_score = (surface_fit * 0.55 + distance_fit * 0.45) * 100
```

未登録種牡馬は中立値 `50` とする。

## 持ちタイム指数

過去走の走破時計を、芝/ダート、距離、競馬場、馬場状態、クラスを考慮して標準化する。

初期式:

```text
raw_time_score = course_par_time - horse_finish_time
time_index = 50 + raw_time_score / course_std_seconds * 10
```

`course_par_time` と `course_std_seconds` は蓄積データから条件別に更新する。

条件別サンプルが少ない場合は、以下の順でフォールバックする。

```text
競馬場 + surface + distance
surface + distance
surface + distance_band
全体
```

## 末脚指数

過去走の上がり3F、着差、通過順の変化を使う。

初期要素:

- 上がり3Fのレース内順位
- 上がり3Fの条件平均との差
- 4角からゴールまでの順位上昇
- 着差が小さい好走

初期式:

```text
closing_index =
  normalized_last3f * 0.55
  + position_gain_score * 0.25
  + close_finish_score * 0.20
```

近走重み:

```text
1走前: 1.00
2走前: 0.72
3走前: 0.52
4走前: 0.36
```

## 先行力指数

過去走の序盤から中盤の通過順を使う。

初期要素:

- 1角または2角通過順
- 3角通過順
- 頭数に対する相対位置
- 先行位置を複数走で維持している安定性

初期式:

```text
early_position_score = 1 - (first_available_corner_position - 1) / max(field_size - 1, 1)
pace_index = weighted_average(early_position_score) * 100
```

逃げ・先行有利な条件では、最終スコアに加点する。差し有利な条件では加点を抑える。

## 予想スコアへの統合

既存スコアを `base_score` とし、指数を以下のように加算する。

```text
final_score =
  base_score
  + sire_fit_score * 0.08
  + time_index * 0.10
  + closing_index * 0.08
  + pace_index * 0.06
```

係数は初期値であり、的中結果を見ながら調整する。

## OCIバッチ処理

1回の起動で以下を行う。

1. 実行日または次開催日のJRA開催有無を確認
2. 開催なしなら正常終了
3. 出走表、結果、過去走を差分取得
4. SQLiteへupsert
5. 種牡馬適性を読み込み
6. 出走馬単位の指数を計算
7. 公開用特徴量ファイルを出力
8. 必要に応じてGitHub Actions `workflow_dispatch` を呼ぶ

## 失敗時の扱い

- データ取得失敗: リトライ後、前回特徴量を残す
- 一部レース失敗: 成功分のみ保存し、失敗レースをログへ記録
- SQLite破損対策: 更新前にバックアップを作成
- Actions dispatch失敗: OCI側バッチは失敗扱いにし、ログで検知

## GitHub Actionsとの接続

GitHub Actionsは過去データDBを持たない。OCIが生成した公開用特徴量ファイルを参照する。

初期案:

- OCIが `site-dist/features-jra.json` 相当の軽量JSONを生成
- GitHub Actionsは将来的にそのJSONを取得して `jra_site_updater.py` に渡す

より安定した案:

- OCIがGitHub repository dispatchまたはworkflow dispatchを呼ぶ
- Actions側がOCI生成物を取得
- Cloudflare Pagesへデプロイ

## 実装段階

### Phase 1

- `data/Sire_data.csv` を静的参照として追加
- SQLiteスキーマを作成
- 種牡馬適性の読み込みと血統補正計算を実装
- OCI用systemd timer定義を追加

### Phase 2

- 過去走データの保存スキーマを固める
- 持ちタイム指数を実装
- 末脚指数を実装
- 先行力指数を実装

### Phase 3

- `jra_site_updater.py` へ特徴量JSONを合流
- 予想スコアへ指数を加算
- 的中検証ログを保存

### Phase 4

- 係数調整
- 条件別チューニング
- データ欠損時のフォールバック改善
