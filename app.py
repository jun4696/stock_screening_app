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
    delete_screening_result,
    export_csv_bytes,
    get_all_results,
    get_results_by_date,
    get_run_summary,
    get_stock_history,
    get_streak_ranking,
    init_db,
    get_db,
    run_screening,
)

load_dotenv()

# APIキー確認
EDINETDB_KEY = os.getenv("EDINETDB_API_KEY")
JQUANTS_KEY  = os.getenv("JQUANTS_API_KEY")


def _delete_option_label(row: dict) -> str:
    run_date = row.get("run_date", "")
    sec_code = row.get("sec_code", "")
    name = row.get("name", "")
    ratio = row.get("net_cash_ratio")
    ratio_text = f" / NC比率 {ratio}%" if ratio is not None else ""
    return f"{run_date} / {sec_code} / {name}{ratio_text}"


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

# DB初期化（初回のみテーブル作成）
with get_db() as conn:
    init_db(conn)

# ----------------------------------------------------------------
# サイドバー: APIキー状態
# ----------------------------------------------------------------
with st.sidebar:
    st.title("📈 株式スクリーニング")
    st.divider()

    edinet_ok = bool(EDINETDB_KEY)
    jquants_ok = bool(JQUANTS_KEY)
    st.markdown("**API接続状態**")
    st.write("EDINET DB :", "✅ 接続済み" if edinet_ok else "❌ 未設定")
    st.write("J-Quants  :", "✅ 接続済み" if jquants_ok else "❌ 未設定")

    if not edinet_ok:
        st.warning("`.env` ファイルにEDINET DB APIキーを設定してください。")
    if not jquants_ok:
        st.info("J-Quants APIキーが未設定のため、現在株価は空欄になります。")

    st.divider()
    page = st.radio(
        "ページ",
        ["🔍 スクリーニング実行", "📊 履歴・銘柄追跡", "📥 CSVダウンロード"],
    )

# ================================================================
# ページ: スクリーニング実行
# ================================================================
if page == "🔍 スクリーニング実行":
    st.title("🔍 スクリーニング実行")
    st.caption("条件を設定して「実行」を押してください。結果はDBに自動保存されます。")

    # ---- 条件設定フォーム ----
    st.subheader("スクリーニング条件")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**EDINET DB（財務条件）**")
        st.info("流動資産 > 負債合計の銘柄を対象にします。")
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

    with col3:
        st.markdown("**補足条件**")
        st.info("流動資産 > 負債合計 は常に適用されます。")
        st.write("")
        st.write(f"実行日: **{date.today().isoformat()}**")

    st.divider()

    # ---- 実行ボタン ----
    if st.button("▶ スクリーニングを実行", type="primary", disabled=not edinet_ok):
        screener_params = {
            "per_lte": per_max,
            "pbr_lte": pbr_max,
            "market_cap_lte": market_cap_max * 100,
            "sort": "market_cap",
        }

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
        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        col_a.metric("取得候補",          stats["candidates"])
        col_b.metric("処理済み",          stats.get("processed", 0))
        col_c.metric("条件クリア",        len(results))
        col_d.metric("キャッシュ利用",    stats["cache_hit"])
        col_e.metric("スキップ",          stats["skipped"])

        if not results:
            st.warning("条件に合う銘柄がありませんでした。条件を緩めてみてください。")
        else:
            df = _results_to_df(results)
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.download_button(
                label="📥 CSVダウンロード",
                data=export_csv_bytes(results),
                file_name=f"screening_{date.today().isoformat()}.csv",
                mime="text/csv",
            )

        st.caption("※ 現在株価のみJ-Quantsから取得。PER・PBR・時価総額と財務指標はEDINET DBベース。")


# ================================================================
# ページ: 履歴・銘柄追跡
# ================================================================
elif page == "📊 履歴・銘柄追跡":
    st.title("📊 履歴・銘柄追跡")

    tab1, tab2, tab3 = st.tabs(["実行履歴サマリー", "日別結果", "銘柄別追跡"])

    # ---- タブ1: 実行履歴サマリー ----
    with tab1:
        st.subheader("実行履歴サマリー（直近20回）")
        summary = get_run_summary()

        if not summary:
            st.info("まだスクリーニングを実行していません。")
        else:
            df_summary = pd.DataFrame(summary)
            df_summary.columns = ["実行日", "ヒット数"]

            col1, col2 = st.columns([2, 1])
            with col1:
                st.bar_chart(df_summary.set_index("実行日")["ヒット数"])
            with col2:
                st.dataframe(df_summary, use_container_width=True, hide_index=True)

        # 連続ヒットランキング
        st.subheader("連続ヒットランキング")
        min_hits = st.slider("最低ヒット回数", 1, 10, 2)
        streak   = get_streak_ranking(min_hits)

        if not streak:
            st.info(f"{min_hits}回以上ヒットした銘柄はまだありません。")
        else:
            df_streak = pd.DataFrame(streak)
            df_streak.columns = ["証券コード", "社名", "累計ヒット", "連続ヒット", "初回", "最終"]
            st.dataframe(df_streak, use_container_width=True, hide_index=True)

    # ---- タブ2: 日別結果 ----
    with tab2:
        st.subheader("日別スクリーニング結果")
        summary = get_run_summary()

        if not summary:
            st.info("まだスクリーニングを実行していません。")
        else:
            run_dates  = [r["run_date"] for r in summary]
            selected   = st.selectbox("実行日を選択", run_dates)
            day_results = get_results_by_date(selected)

            if day_results:
                df = _results_to_df(day_results)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    label="📥 このCSVをダウンロード",
                    data=export_csv_bytes(day_results),
                    file_name=f"screening_{selected}.csv",
                    mime="text/csv",
                )

                st.divider()
                st.subheader("履歴レコード削除")
                delete_target = st.selectbox(
                    "削除する銘柄履歴を選択",
                    day_results,
                    format_func=_delete_option_label,
                    key=f"delete_day_{selected}",
                )
                confirm_delete = st.checkbox(
                    "この1件を履歴から削除する",
                    key=f"confirm_delete_day_{selected}",
                )
                if st.button("選択した履歴を削除", type="secondary", disabled=not confirm_delete, key=f"delete_day_button_{selected}"):
                    if delete_screening_result(int(delete_target["id"])):
                        st.success("履歴を1件削除しました。")
                        st.rerun()
                    else:
                        st.error("削除対象が見つかりませんでした。画面を更新してください。")
            else:
                st.info("この日の結果はありません。")

    # ---- タブ3: 銘柄別追跡 ----
    with tab3:
        st.subheader("銘柄別 出現履歴")
        sec_code_input = st.text_input("証券コード（4桁）を入力", placeholder="例: 7203")

        if sec_code_input:
            history = get_stock_history(sec_code_input.strip())

            if not history:
                st.warning(f"証券コード {sec_code_input} の履歴はありません。")
            else:
                name = history[0].get("name", sec_code_input) if history else sec_code_input
                st.markdown(f"**{name}（{sec_code_input}）** — 合計 {len(history)}回ヒット")

                df_hist = pd.DataFrame(history)
                df_hist = df_hist[["run_date", "close_price", "per", "pbr", "gap_oku", "market_cap_oku", "net_cash_ratio"]]
                df_hist.columns = ["日付", "現在株価(円)", "PER(倍)", "PBR(倍)", "差額(億円)", "時価総額(億円)", "ネットキャッシュ比率(%)"]

                st.dataframe(df_hist, use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("この銘柄の履歴削除")
                delete_target = st.selectbox(
                    "削除する履歴を選択",
                    history,
                    format_func=_delete_option_label,
                    key=f"delete_stock_{sec_code_input.strip()}",
                )
                confirm_delete = st.checkbox(
                    "この1件を履歴から削除する",
                    key=f"confirm_delete_stock_{sec_code_input.strip()}",
                )
                if st.button("選択した履歴を削除", type="secondary", disabled=not confirm_delete, key=f"delete_stock_button_{sec_code_input.strip()}"):
                    if delete_screening_result(int(delete_target["id"])):
                        st.success("履歴を1件削除しました。")
                        st.rerun()
                    else:
                        st.error("削除対象が見つかりませんでした。画面を更新してください。")


# ================================================================
# ページ: CSVダウンロード
# ================================================================
elif page == "📥 CSVダウンロード":
    st.title("📥 CSVダウンロード")
    st.caption("蓄積された全履歴を一括でダウンロードできます。")

    all_results = get_all_results()

    if not all_results:
        st.info("まだスクリーニング結果がありません。")
    else:
        st.metric("総レコード数", f"{len(all_results)}件")

        st.download_button(
            label="📥 全履歴をCSVダウンロード",
            data=export_csv_bytes(all_results),
            file_name=f"screening_all_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

        # プレビュー
        st.subheader("プレビュー（直近20件）")
        df_all = _results_to_df(all_results[:20])
        st.dataframe(df_all, use_container_width=True, hide_index=True)
