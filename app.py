"""
app.py — Streamlit フロントエンド

起動方法:
  streamlit run app.py
  または docker compose up
"""

import os
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from screening import (
    export_csv_bytes,
    init_db,
    get_db,
    run_screening,
)

load_dotenv()

# APIキー確認
EDINETDB_KEY = os.getenv("EDINETDB_API_KEY")
JQUANTS_KEY  = os.getenv("JQUANTS_API_KEY")


INDUSTRIES = [
    "水産・農林業",
    "鉱業",
    "建設業",
    "食料品",
    "繊維製品",
    "パルプ・紙",
    "化学",
    "医薬品",
    "石油・石炭製品",
    "ゴム製品",
    "ガラス・土石製品",
    "鉄鋼",
    "非鉄金属",
    "金属製品",
    "機械",
    "電気機器",
    "輸送用機器",
    "精密機器",
    "その他製品",
    "電気・ガス業",
    "陸運業",
    "海運業",
    "空運業",
    "倉庫・運輸関連",
    "情報・通信業",
    "卸売業",
    "小売業",
    "銀行業",
    "証券、商品先物取引業",
    "保険業",
    "その他金融業",
    "不動産業",
    "サービス業",
]


def _inject_theme_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+JP:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", "IBM Plex Sans JP", -apple-system, sans-serif;
        }

        .block-container {
            padding-top: 32px;
            padding-bottom: 48px;
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 24px;
        }

        h1, h2, h3 {
            font-weight: 600;
            letter-spacing: -0.01em;
        }

        /* ステータス表示ラベル（サイドバー「API接続状態」等） */
        .status-label {
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #5B6472;
        }
        .status-ok { color: #1F8A5F; font-weight: 500; }
        .status-ng { color: #C0392B; font-weight: 500; }

        /* ボタン: primaryColorはconfig.tomlのテーマが担当。ここは押下フィードバックのみ */
        .stButton > button, .stDownloadButton > button {
            border-radius: 6px;
            transition: transform 150ms ease-out, background-color 150ms ease-out;
        }
        .stButton > button:active, .stDownloadButton > button:active {
            transform: scale(0.97);
        }

        /* 指標: 数値は桁が揃うtabular-nums */
        [data-testid="stMetricValue"] {
            font-variant-numeric: tabular-nums;
        }
        [data-testid="stMetricLabel"] {
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #5B6472;
        }

        /* 主要指標（条件クリア件数）— st.metricでなく単独HTMLで組む */
        .primary-metric {
            margin-bottom: 8px;
        }
        .primary-metric .primary-metric-label {
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #5B6472;
        }
        .primary-metric .primary-metric-value {
            font-family: "IBM Plex Mono", monospace;
            font-variant-numeric: tabular-nums;
            font-size: 2.75rem;
            font-weight: 500;
            color: #0E7C5A;
            line-height: 1.2;
        }

        /* アラート類はベタ塗りでなくヘアライン基調に（内側のBaseWeb通知要素まで上書き） */
        [data-testid="stAlert"] [data-baseweb="notification"] {
            background-color: #FFFFFF !important;
            border: 1px solid rgba(20, 24, 31, 0.10);
            box-shadow: none;
            color: #14181F;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _results_to_df(results: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(results)
    if df.empty:
        return df

    cols = {
        "name":              "社名",
        "sec_code":          "証券コード",
        "fiscal_year":       "決算期",
        "close_price":       "現在株価(円)",
        "current_assets":    "流動資産(億円)",
        "total_liabilities": "負債合計(億円)",
        "gap_oku":           "差額(億円)",
        "net_cash_ratio":    "ネットキャッシュ比率(%)",
        "dividend_yield":    "配当利回り(%)",
        "per":               "PER(倍)",
        "pbr":               "PBR(倍)",
        "market_cap_oku":    "時価総額(億円)",
        "run_date":          "実行日",
    }
    df = df.rename(columns=cols)
    ordered = [v for v in cols.values() if v in df.columns]
    return df[ordered]


# ----------------------------------------------------------------
# ページ設定
# ----------------------------------------------------------------
st.set_page_config(
    page_title="株式スクリーニングツール",
    page_icon="📈",
    layout="wide",
)
_inject_theme_css()

# 財務データキャッシュ用DB初期化（初回のみテーブル作成）
with get_db() as conn:
    init_db(conn)

# ----------------------------------------------------------------
# サイドバー: APIキー状態
# ----------------------------------------------------------------
with st.sidebar:
    st.title("株式スクリーニング")
    st.divider()

    edinet_ok = bool(EDINETDB_KEY)
    jquants_ok = bool(JQUANTS_KEY)
    st.markdown('<div class="status-label">API接続状態</div>', unsafe_allow_html=True)
    st.markdown(
        f'EDINET DB&nbsp;&nbsp;<span class="{"status-ok" if edinet_ok else "status-ng"}">'
        f'{"接続済み" if edinet_ok else "未設定"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'J-Quants&nbsp;&nbsp;&nbsp;<span class="{"status-ok" if jquants_ok else "status-ng"}">'
        f'{"接続済み" if jquants_ok else "未設定"}</span>',
        unsafe_allow_html=True,
    )

    if not edinet_ok:
        st.warning("`.env` ファイルにEDINET DB APIキーを設定してください。")
    if not jquants_ok:
        st.info("J-Quants APIキーが未設定のため、現在株価は空欄になります。")

# ================================================================
# スクリーニング実行
# ================================================================
st.title("スクリーニング実行")
st.caption("条件を設定して「実行」を押してください。結果はこの画面に表示され、CSVでダウンロードできます。")

# ---- 条件設定フォーム ----
st.subheader("スクリーニング条件")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**EDINET DB（財務条件）**")
    st.info("流動資産 > 負債合計の銘柄を対象にします。")
    selected_industry = st.selectbox("業種", ["すべて"] + INDUSTRIES)
    candidate_limit = st.number_input(
        "最大取得件数",
        min_value=1,
        max_value=1000,
        value=30,
        step=10,
        help="EDINET DBから詳細財務データを確認する最大候補数です。Free枠では小さめにしてください。",
    )

with col2:
    st.markdown("**EDINET DB（市場指標）**")
    per_max        = st.number_input("PER 以下（倍）",      value=8.0,  step=0.5)
    pbr_max        = st.number_input("PBR 以下（倍）",      value=0.8,  step=0.1)
    market_cap_max = st.number_input("時価総額 以下（億円）", value=500,  step=50)
    net_cash_ratio_min = st.number_input("ネットキャッシュ比率 以上（%）", value=0.0, step=5.0)
    dividend_yield_min = st.number_input("配当利回り 以上（%）", value=4.0, step=0.5)

with col3:
    st.markdown("**補足条件**")
    st.info("流動資産 > 負債合計 は常に適用されます。")
    st.write("")
    st.write(f"実行日: **{date.today().isoformat()}**")

st.divider()

# ---- 実行ボタン ----
if st.button(
    "スクリーニングを実行",
    type="primary",
    disabled=not edinet_ok,
):
    screener_params = {
        "per_lte": per_max,
        "pbr_lte": pbr_max,
        "market_cap_lte": market_cap_max * 100,
        "dividend_yield_gte": dividend_yield_min,
        "sort": "market_cap",
    }
    if selected_industry != "すべて":
        screener_params["industry"] = selected_industry

    progress_text = st.empty()
    progress_bar  = st.progress(0)

    def on_progress(current: int, total: int, message: str):
        progress_text.text(f"処理中: {message}")
        progress_bar.progress(current / total)

    try:
        with st.spinner("スクリーニング中..."):
            results, stats = run_screening(
                params=screener_params,
                per_max=per_max,
                pbr_max=pbr_max,
                market_cap_max=market_cap_max,
                net_cash_ratio_min=net_cash_ratio_min,
                dividend_yield_min=dividend_yield_min,
                candidate_limit=candidate_limit,
                progress_cb=on_progress,
            )
    except RuntimeError as e:
        st.error(f"エラー: {e}")
        st.stop()

    progress_bar.empty()
    progress_text.empty()

    # ---- 結果表示 ----
    st.subheader("実行結果")

    st.markdown(
        f'<div class="primary-metric">'
        f'<div class="primary-metric-label">条件クリア</div>'
        f'<div class="primary-metric-value">{len(results)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("取得候補",       stats["candidates"])
    col_b.metric("処理済み",       stats.get("processed", 0))
    col_c.metric("キャッシュ利用", stats["cache_hit"])
    col_d.metric("スキップ",       stats["skipped"])

    if not results:
        st.warning("条件に合う銘柄がありませんでした。条件を緩めてみてください。")
    else:
        df = _results_to_df(results)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.download_button(
            label="CSVダウンロード",
            data=export_csv_bytes(results),
            file_name=f"screening_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

    st.caption("※ 現在株価のみJ-Quantsから取得。PER・PBR・時価総額と財務指標はEDINET DBベース。")
