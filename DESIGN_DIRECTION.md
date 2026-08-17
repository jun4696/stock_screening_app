# 方向宣言: 株式スクリーニングツール

- ジョブ: 財務条件でバリュー株を絞り込み、結果を一望・CSV出力する実務ツール
- レジスター: 主=精密（Operational Calm / Linear・Stripe系）。信頼と速度優先、フィンテック文脈のため祝祭演出は禁じ手。副=なし
- サーフェス: web（Streamlitレンダリングの単一ページ）
- パレット（役割つき実HEX）:
  - 地: `#FAFAF8` / 面: `#FFFFFF` / 文字: `#14181F` / 副文字: `#5B6472`
  - アクセント: `#0E7C5A`（用途: 実行ボタン・選択状態・フォーカスリング・主要指標の強調のみ。面に塗らず線・文字・数値に使う）
  - セマンティック: 成功(条件クリア/接続済み)=`#1F8A5F` 警告(未設定)=`#B7791F` 危険(エラー)=`#C0392B`
  - ヘアライン: `rgba(20,24,31,.10)`
- タイポ: display/body = IBM Plex Sans（欧文）+ IBM Plex Sans JP（和文）、utility(数値) = IBM Plex Mono + tabular-nums、スケール比 = 1.2、和欧混植 = `"IBM Plex Sans","IBM Plex Sans JP",sans-serif`
- 余白リズム: 8ptグリッド、セクション間32px、要素間16px、フォーム項目間12px
- モーション: 基準150ms ease-out、押下scale(0.97)、祝祭なし、reduced-motion対応（transform/opacityのみ使用）
- シグネチャー: 実行結果の5指標を同重量で並べない。「条件クリア」件数だけをアクセント色・大サイズで独立させ、他4指標（取得候補・処理済み・キャッシュ利用・スキップ）を1段沈めた副指標列にする——スクリーニングの主役=何件当たったか、を視覚的に一発で伝える
- 禁じ手: 絵文字ラベル（📈🔍▶📥✅❌の代替: Streamlit 1.35は`st.button`/`st.download_button`の`icon=`パラメータに非対応のため、絵文字を使わずテキストのみで表現。ステータスは色+テキストのみ）、カード乱立、Streamlit既定の赤系プライマリ・既定フォントの放置

## 実装上の既知の制約

- Streamlit 1.35は`.streamlit/config.toml`でのカスタムfont-family指定に非対応。フォントは`app.py`側のCSS注入（`@import` + `<style>`）で当てる。オフライン時は欧文フォールバック（`-apple-system, sans-serif`）に自動退避する。
- `st.dataframe`（結果テーブル）はStreamlit 1.19以降canvasベースのglide-data-gridで描画されるため、行hover・フォント・tabular-numsを外部CSSで直接制御できない。桁区切り・小数桁は`column_config.NumberColumn(format=...)`で担保し、グリッド内部の完全な意匠統一はスコープ外とする。
- 本改修は見た目（Streamlitコンポーネントの構成・スタイル）のみ。`screening.py`のロジック・DBスキーマ・APIコールは無変更。
