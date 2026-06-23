# TOKYO12R スクレイピング取得元調査

調査日: 2026-06-23 JST

## 結論

一次取得元は JRA 公式サイトに寄せる。許諾データの利用は前提にせず、公開HTMLから開催日程、出馬表、レース条件、競走馬、騎手、調教師、過去成績、結果照合に必要な情報を取得する。

公開サイトには出走表や馬柱を再掲しない。取得データは内部予想処理だけに使い、公開JSONは「印、馬名、買い目、更新時刻、開催有無」に限定する。

## 候補一覧

| サイト | 判定 | メモ |
| --- | --- | --- |
| JRA公式 | 主取得元 | `https://www.jra.go.jp/robots.txt` は `User-agent: * Disallow:`。利用案内ではJRA掲載物の二次利用に注意が必要なため、取得データの公開再掲は避ける。 |
| スポーツナビ競馬 | 照合候補 | `https://sports.yahoo.co.jp/keiba/` で日程・結果・重賞情報がHTMLでも一部読める。LINEヤフー共通利用規約ではサービス目的外利用や再利用が制限されるため主取得元にしない。 |
| netkeiba | 除外 | 出馬表・レース一覧は技術的に取得しやすいが、利用規約で私的利用範囲外の複製・販売・出版、営業利用が制限されている。 |
| 競馬ラボ | 除外 | `robots.txt` は競馬DBの全面禁止ではないが、利用規約とフッターで営利利用、無断複製、転載が制限されている。 |
| デイリー うま屋 | 保留 | `robots.txt` は広く許可寄り。JRA/NARのレース導線があるが、新聞社の予想・記事コンテンツは取得元にしない。 |
| 東スポ競馬 | 保留 | 一般User-Agentはrobots上許可寄りでレース情報導線あり。ただしAI系User-Agentはブロック。予想・記事コンテンツは取得元にしない。 |
| サンスポ / 日刊スポーツ / スポニチ / 馬トク報知 / 中日スポーツ | 非主力 | 多くが記事中心で、AI系またはScrapy系User-Agentをrobotsでブロック。馬柱の安定取得元としてはJRA公式より不利。 |
| Umanity | 非主力 | robotsで複数のクローラをブロック。利用規約とページ構造の追加確認が必要なため主取得元にしない。 |

## 実装時の制約

- User-Agentを明示する。
- 取得頻度は最小限にする。
- robots.txtの差分を定期確認する。
- HTML構造が変わったら予想生成を止め、古いデータを公開しない。
- 内部rawデータは短期保持にする。
- 公開前に、出走表・馬柱由来の列が公開JSONに混入していないか検査する。

## 参照URL

- JRA robots.txt: https://www.jra.go.jp/robots.txt
- JRA ご利用に際して: https://www.jra.go.jp/use/
- JRA 競馬メニュー: https://www.jra.go.jp/keiba/
- スポーツナビ競馬: https://sports.yahoo.co.jp/keiba/
- LINEヤフー共通利用規約: https://www.lycorp.co.jp/ja/company/terms/
- netkeiba 利用規約: https://www.netkeiba.com/info/kiyaku.html
- 競馬ラボ robots.txt: https://www.keibalab.jp/robots.txt
- 競馬ラボ 利用規約: https://www.keibalab.jp/info/agreement.html
- デイリー うま屋: https://www.daily.co.jp/umaya/
- 東スポ競馬: https://tospo-keiba.jp/
