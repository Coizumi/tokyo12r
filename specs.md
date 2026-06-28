# TOKYO12R JRA Feature Pipeline Specs

## 目的

TOKYO12R by ZIN のJRA予想を、現在の軽量ヒューリスティックから、過去競走データに基づく指数型へ拡張する。

対象指数:

- 血統補正: レース条件、芝/ダートと距離に対する父および母の父の種牡馬適性
- 持ちタイム指数: 同条件または近似条件での走破時計評価
- 末脚指数: 上がり性能、終盤加速、差し脚の評価
- 先行力指数: 序盤位置取り、通過順、先行安定性の評価

## 基本方針

GitHub Actionsには重いデータ収集や過去データ再計算を載せない。

役割分担:

- WebARENA Indigo VPS: データ収集、SQLite蓄積、指数計算、的中判定、週/月/年サマリー生成、公開用特徴量ファイル生成
- GitHub Actions: 公開HTML生成、Cloudflare Pagesデプロイ、必要に応じた手動/dispatch実行
- Cloudflare Pages: 静的サイト配信

WebARENA Indigo は 2GB プランを標準構成とする。

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

VPS側は差分更新とSQLite中心で構成する。全量再取得や重い機械学習は初期対象外とする。

VPSはWebサーバーとして公開しない。公開はCloudflare Pagesに寄せ、VPSはバックエンドバッチと永続DBに限定する。

OCI無料利用枠は、A1 Flexの容量不足とE2.1.Microの実運用余力不足が確認されたため、標準構成から外す。既存のOCI検証リソースは移行前に削除する。

## サイト構成

公開サイトは `https://tokyo12r.byzin.win/` をTOKYO12Rの本体とし、ポータル、JRA予想、地方競馬、JRA結果を明確に分ける。

右上ナビゲーションは、予想ページと結果ページで共通して以下の順にする。

```text
TOP              => https://byzin.win/
TOKYO12R         => https://tokyo12r.byzin.win/   (現在ページの再読み込み)
地方競馬 Today   => https://nar.byzin.win/
結果             => /resultYYYYMMDD.html
```

表示ラベルもこの順序を維持する。`NAR` の省略表記は使わず、利用者が遷移先を理解できる `地方競馬 Today` とする。

### 計測/広告タグ

TOKYO12Rの公開HTMLは、全ページの `<head>` 内にGoogle AnalyticsとGoogle AdSenseのタグを配置する。

- Google Analytics 測定ID: `G-TG6LR51391`
- Google AdSense publisher ID: `ca-pub-6637962622384846`

対象ページ:

- `index.html`
- `resultYYYYMMDD.html`

### 予想ページ

予想ページは当日または対象開催日のJRA予想を表示する。

構成:

- ヘッダー: ブランド名と右上ナビゲーション
- ヒーロー: TOKYO12Rの視覚要素
- サマリー: 対象日、更新時刻
- 開催場タブ: 開催場ごとにタブを表示し、選択中の開催場だけを表示する
- レースカード一覧: 選択中の開催場のレースカードを、地方競馬 Today と同じカードグリッドで表示する
- レースカード: レース番号、レース名、条件、発走時刻、予想印、買い目、結果ページへのリンク
- フッター: 年齢注意などの補足

開催場表示は地方競馬 Today と同じタブ型にする。

- タブ要素: `.venue-tabs`, `.venue-tab`
- パネル要素: `.venue[role="tabpanel"]`
- レース一覧: `.race-list`
- レースカード: `.race-card`
- タブ切替: `/assets/site.js` で `data-venue-tab` と `data-venue-panel` を同期する
- 初期表示: 先頭の開催場を選択状態にする
- URL hashが `#venue-1` などの開催場IDを指す場合は、その開催場を初期表示する

予想ページの各レースカードには、結果ページの該当レースへ移動するリンクを必ず表示する。

```text
/resultYYYYMMDD.html#race-<venue-key>-<race-no>
```

結果が未確定でもリンク先のアンカーは結果ページ側に存在させる。これにより、結果確定前後でリンクの有無やジャンプ先が変わらないようにする。

### 結果ページ

結果ページは `nar.byzin.win` の結果ページと同じく、横並びカードではなく1本の縦方向の柱として表示する。

構成:

- ヘッダー: ブランド名と右上ナビゲーション
- サマリー: 対象日、更新時刻、結果取得状態
- 結果本文: 1カラムの縦並び
- 開催場見出し: 東京、阪神、函館など開催場ごとに区切る
- レース結果カード: 開催場内でレース番号昇順に並べる
- フッター: JRA公式トップページへのリンクと注意文

レース結果カードは、以下の情報を表示する。

- アンカーID: `race-<venue-key>-<race-no>`
- レース番号: `1R` から `12R`
- レース名
- 条件
- 発走時刻
- 1着、2着、3着の馬番と馬名
- 公開済み予想印
- 買い目ごとの的中結果

1着、2着、3着の表示形式:

```text
1着  <馬番> <馬名>
2着  <馬番> <馬名>
3着  <馬番> <馬名>
```

結果未確定のレースは、同じアンカーIDを持つカードを表示し、着順欄には `結果未確定` と表示する。

### 結果ページのアンカー調整

予想ページから結果ページへ遷移したとき、固定ヘッダーによりレース番号が隠れないようにする。

CSS要件:

```css
.result-race-card {
  scroll-margin-top: 96px;
}

@media (max-width: 640px) {
  .result-race-card {
    scroll-margin-top: 132px;
  }
}
```

実装時のクラス名は既存CSSに合わせてよいが、レースカードのアンカー対象要素に十分な `scroll-margin-top` を設定する。

### 買い目結果の表示

結果ページでは、買い目ごとに的中/不的中/未確定を視覚的に分ける。

買い目の生成対象:

- 馬連フォーメーション
- 3連複BOX
- 3連単フォーメーション

`穴狙い馬単` は生成対象から外す。3連単フォーメーションが的中する着順では、☆1着固定の馬単は必ず不的中になり、結果ページで不必要な不的中表示が増えるため。

的中判定は実際の着順位置を保持して行う。対象着順に予想印のない馬が含まれる場合、その買い目は不的中とする。

- 馬連: 実際の1着・2着の馬が両方とも予想印内にあり、その組み合わせが買い目に含まれる場合のみ的中
- 3連複: 実際の1着・2着・3着の馬がすべて予想印内にあり、その組み合わせが買い目に含まれる場合のみ的中
- 3連単: 実際の1着・2着・3着の馬がすべて予想印内にあり、その順序が買い目に含まれる場合のみ的中

的中した買い目:

- 払戻額を表示する
- 明るめのオレンジ系背景で表示する
- 文字色は十分なコントラストを確保する
- 例: `払戻 12,340円`

推奨色:

```text
background: #fff3d6
border:     #f2b866
text:       #6f3d00
amount:     #b45309
```

的中していない買い目:

- 中間調のグレー背景で表示する
- 払戻額は表示しない
- `不的中` または `払戻 0円` のどちらかに統一する

推奨色:

```text
background: #e5e7eb
border:     #cbd5e1
text:       #374151
```

未確定の買い目:

- 低彩度の薄い背景で表示する
- `結果未確定` と表示する
- 的中/不的中とは別状態として扱う

### 公式情報へのリンク

結果ページでは、各レースカード内にJRA公式結果への個別リンクを表示しない。

ページ最下部にのみJRA公式トップページへのリンクを置き、次の文言を必ず表示する。

```text
正確な情報は公式情報を参照ください。
```

フッター例:

```html
<footer>
  <a href="https://www.jra.go.jp/">JRA公式サイト</a>
  <span>正確な情報は公式情報を参照ください。</span>
</footer>
```

## 更新スケジュール

VPSのtimezoneを `Asia/Tokyo` に設定する。

通常更新:

- 金曜 22:00 JST
- 土曜 09:32, 10:32, ..., 17:32 JST
- 日曜 09:32, 10:32, ..., 17:32 JST
- 月曜 09:32, 10:32, ..., 17:32 JST
- 火曜 09:32, 10:32, ..., 17:32 JST

月曜・火曜は開催がある場合のみ実処理する。スケジュール自体は毎週起動し、スクリプト側で開催なしなら正常終了する。

最大実行回数は週37回程度。

## データ保存

VPS上のSQLiteを主ストアとする。

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
- `predictions`: 公開した予想印
- `bet_tickets`: 生成した買い目
- `race_results`: 確定着順
- `payouts`: 払戻
- `bet_outcomes`: 的中判定と損益
- `performance_summaries`: 週間、月間、年間サマリー
- `pipeline_runs`: バッチ実行履歴

公開用には、SQLite全体ではなく軽量JSON/CSVのみを出力する。

## 的中結果の蓄積

VPSは、公開済み予想と確定結果を同じSQLiteに保存し、買い目単位で的中判定を行う。

保存単位:

- レース単位: 開催日、場、R、条件、発走時刻、結果取得状態
- 予想単位: 印、馬名、馬番、人気状態、生成時刻
- 買い目単位: 式別、組み合わせ、点数、想定購入額
- 結果単位: 着順、馬番、馬名、払戻、確定時刻
- 的中単位: 的中有無、払戻額、投資額、回収額、収支

初期の購入額は1点100円換算とする。実購入額ではなく、回収率比較のための仮想集計値として扱う。

サマリー粒度:

```text
weekly  = ISO年 + ISO週
monthly = YYYY-MM
yearly  = YYYY
```

サマリー項目:

- レース数
- 買い目点数
- 的中点数
- 投資額
- 払戻額
- 収支
- 的中率
- 回収率

サマリーは `bet_outcomes` から再計算可能にする。係数変更や買い目変更後も、履歴データから再集計できるようにする。

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
芝     => 100
ダート => -100
障害   => 0
```

父または母の父に対する適性計算:

```text
surface_fit = 1 - min(abs(sire.surface_axis - race_surface_axis), 200) / 200
distance_fit = 1 - min(abs(sire.distance_m - race_distance_m), 600) / 600
lineage_fit_score = (surface_fit * 0.55 + distance_fit * 0.45) * 100
```

血統補正の初期式:

```text
sire_score = lineage_fit_score(sire_name)
dam_sire_score = lineage_fit_score(dam_sire_name)
sire_fit_score = min(100, sire_score + max(0, (dam_sire_score - 50) * 0.35))
```

未登録種牡馬は中立値 `50` とする。母の父は加点要素のみとし、父の評価を下げる減点には使わない。

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

## VPSバッチ処理

1回の起動で以下を行う。

1. 実行日または次開催日のJRA開催有無を確認
2. 開催なしなら正常終了
3. 出走表、結果、過去走を差分取得
4. SQLiteへupsert
5. 種牡馬適性を読み込み
6. 出走馬単位の指数を計算
7. 公開用特徴量ファイルを出力
8. 必要に応じてGitHub Actions `workflow_dispatch` を呼ぶ

systemd timerで `scripts/jra_oci_batch.py` 相当のバッチを実行する。既存コード名にOCIが残る場合も、実行先はWebARENA Indigo VPSとする。後続でファイル名を `jra_vps_batch.py` へ変更できる状態にしておく。

## 失敗時の扱い

- データ取得失敗: リトライ後、前回特徴量を残す
- 一部レース失敗: 成功分のみ保存し、失敗レースをログへ記録
- SQLite破損対策: 更新前にバックアップを作成
- Actions dispatch失敗: VPS側バッチは失敗扱いにし、ログで検知

## GitHub Actionsとの接続

GitHub Actionsは過去データDBを持たない。VPSが生成した公開用特徴量ファイルを参照する。

初期案:

- VPSが `site-dist/features-jra.json` 相当の軽量JSONを生成
- GitHub Actionsは将来的にそのJSONを取得して `jra_site_updater.py` に渡す

より安定した案:

- VPSがGitHub repository dispatchまたはworkflow dispatchを呼ぶ
- Actions側がVPS生成物を取得
- Cloudflare Pagesへデプロイ

## 導入段階

### Phase 1

- WebARENA Indigo 2GB を契約し、Linux VPSを作成
- SSH鍵、ファイアウォール、OS更新、Git/Python/SQLiteを設定
- 既存リポジトリを `/opt/tokyo12r` に配置
- `data/Sire_data.csv` を静的参照として利用
- SQLiteスキーマを作成
- 種牡馬適性の読み込みと血統補正計算を実装
- systemd timer定義を追加

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
