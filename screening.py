"""
screening.py — スクリーニングロジック（UIなし）

StreamlitアプリとCLIの両方から import して使う。
print / st.write は一切行わず、すべて戻り値で結果を返す。
"""

import csv
import io
import logging
import os
import psycopg
from psycopg.rows import dict_row
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Generator

import requests
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# ----------------------------------------------------------------
# 設定
# ----------------------------------------------------------------
load_dotenv()

EDINETDB_KEY = os.getenv("EDINETDB_API_KEY")
JQUANTS_KEY  = os.getenv("JQUANTS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

EDINET_BASE     = "https://edinetdb.jp/v1"
JQUANTS_BASE    = "https://api.jquants.com/v2"
EDINET_HEADERS  = {"X-API-Key": EDINETDB_KEY} if EDINETDB_KEY else {}
JQUANTS_HEADERS = {"x-api-key": JQUANTS_KEY}  if JQUANTS_KEY  else {}

CACHE_DAYS   = 30
API_INTERVAL = 0.3

# CSV ヘッダー（export_csv_bytes でも使用）
CSV_HEADER = [
    "実行日", "社名", "証券コード", "決算期",
    "現在株価(円)", "流動資産(億円)", "負債合計(億円)", "差額(億円)",
    "ネットキャッシュ比率(%)", "PER(倍)", "PBR(倍)", "時価総額(億円)",
]


# ================================================================
# DB ユーティリティ
# ================================================================

@contextmanager
def get_db() -> Generator[psycopg.Connection, None, None]:
    """Postgres接続をコンテキストマネージャで管理。例外時も必ずcloseする。"""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が未設定です。Postgres/Supabase の接続文字列を設定してください。")

    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)
    try:
        yield conn
    finally:
        conn.close()


def init_db(conn: psycopg.Connection) -> None:
    """テーブルとインデックスを初期化する（初回のみ作成）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financials_cache (
            edinet_code       TEXT PRIMARY KEY,
            name              TEXT,
            sec_code          TEXT,
            fiscal_year       INTEGER,
            current_assets    DOUBLE PRECISION,
            total_liabilities DOUBLE PRECISION,
            eps               DOUBLE PRECISION,
            bps               DOUBLE PRECISION,
            shares_issued     BIGINT,
            roa               DOUBLE PRECISION,
            equity_ratio      DOUBLE PRECISION,
            fetched_at        DATE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS screening_results (
            id                BIGSERIAL PRIMARY KEY,
            run_date          DATE,
            sec_code          TEXT,
            name              TEXT,
            fiscal_year       INTEGER,
            close_price       DOUBLE PRECISION,
            current_assets    DOUBLE PRECISION,
            total_liabilities DOUBLE PRECISION,
            gap_oku           DOUBLE PRECISION,
            roa               DOUBLE PRECISION,
            equity_ratio      DOUBLE PRECISION,
            per               DOUBLE PRECISION,
            pbr               DOUBLE PRECISION,
            market_cap_oku    DOUBLE PRECISION,
            net_cash_ratio    DOUBLE PRECISION
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_results_run_date
            ON screening_results(run_date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_results_sec_code
            ON screening_results(sec_code)
    """)
    conn.execute("""
        ALTER TABLE screening_results
        ADD COLUMN IF NOT EXISTS net_cash_ratio DOUBLE PRECISION
    """)
    conn.commit()


def _date_iso(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


# ================================================================
# 財務データキャッシュ
# ================================================================

def get_cached_financials(conn: psycopg.Connection, edinet_code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM financials_cache WHERE edinet_code = %s", (edinet_code,)
    ).fetchone()
    if row is None:
        return None
    if (date.today() - date.fromisoformat(_date_iso(row["fetched_at"]))).days > CACHE_DAYS:
        return None
    return dict(row)


def save_financials_cache(
    conn: psycopg.Connection,
    edinet_code: str,
    name: str,
    sec_code: str,
    data: dict,
) -> None:
    equity_ratio = data.get("equity_ratio_official") or data.get("equity_ratio")
    conn.execute(
        """
        INSERT INTO financials_cache (
            edinet_code, name, sec_code, fiscal_year,
            current_assets, total_liabilities,
            eps, bps, shares_issued, roa, equity_ratio, fetched_at
        ) VALUES (
            %(edinet_code)s, %(name)s, %(sec_code)s, %(fiscal_year)s,
            %(current_assets)s, %(total_liabilities)s,
            %(eps)s, %(bps)s, %(shares_issued)s, %(roa)s, %(equity_ratio)s, %(fetched_at)s
        )
        ON CONFLICT (edinet_code) DO UPDATE SET
            name = EXCLUDED.name,
            sec_code = EXCLUDED.sec_code,
            fiscal_year = EXCLUDED.fiscal_year,
            current_assets = EXCLUDED.current_assets,
            total_liabilities = EXCLUDED.total_liabilities,
            eps = EXCLUDED.eps,
            bps = EXCLUDED.bps,
            shares_issued = EXCLUDED.shares_issued,
            roa = EXCLUDED.roa,
            equity_ratio = EXCLUDED.equity_ratio,
            fetched_at = EXCLUDED.fetched_at
        """,
        {
            "edinet_code":       edinet_code,
            "name":              name,
            "sec_code":          sec_code,
            "fiscal_year":       data.get("fiscal_year"),
            "current_assets":    data.get("current_assets"),
            "total_liabilities": data.get("total_liabilities"),
            "eps":               data.get("eps"),
            "bps":               data.get("bps"),
            "shares_issued":     data.get("shares_issued"),
            "roa":               data.get("roa"),
            "equity_ratio":      equity_ratio,
            "fetched_at":        date.today().isoformat(),
        },
    )


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    if value in (None, "", "?"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ================================================================
# J-Quants 株価取得（メモリキャッシュ付き）
# ================================================================

_price_cache: dict[str, float | None] = {}


def get_latest_close(sec_code4: str) -> float | None:
    """J-Quants V2 APIから直近の終値を返す。同一実行内はキャッシュ。"""
    if sec_code4 in _price_cache:
        return _price_cache[sec_code4]

    code5 = sec_code4 + "0"
    price = None

    for days_ago in range(1, 8):
        target = (date.today() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        try:
            res = requests.get(
                f"{JQUANTS_BASE}/equities/bars/daily",
                params={"code": code5, "date": target},
                headers=JQUANTS_HEADERS,
                timeout=10,
            )
        except requests.RequestException as e:
            log.warning("J-Quants リクエストエラー(%s): %s", sec_code4, e)
            break

        if res.status_code == 200:
            quotes = res.json().get("daily_quotes", [])
            if quotes:
                price = quotes[0].get("Close")
                break

    _price_cache[sec_code4] = price
    return price


# ================================================================
# スクリーニング本体
# ================================================================

def run_screening(
    params: dict,
    per_max: float,
    pbr_max: float,
    market_cap_max: float,
    net_cash_ratio_min: float,
    progress_cb=None,   # Streamlit の st.empty() などを受け取るコールバック
) -> tuple[list[dict], dict]:
    """
    スクリーニングを実行し、結果リストと統計情報を返す。

    Args:
        params:          EDINET DB screener パラメータ
        per_max:         PER上限
        pbr_max:         PBR上限
        market_cap_max:  時価総額上限（億円）
        net_cash_ratio_min: ネットキャッシュ比率下限（%）
        progress_cb:     進捗コールバック。呼ばれるたびに (current, total, message) を受け取る。

    Returns:
        (results, stats)
        results: 条件クリアした銘柄のリスト（dict）
        stats:   {"candidates": int, "cache_hit": int, "skipped": int}
    """
    _price_cache.clear()   # 実行ごとにキャッシュをリセット
    run_date = date.today().isoformat()
    stats = {"candidates": 0, "cache_hit": 0, "skipped": 0}

    # ステップ1: EDINET DBスクリーニング
    try:
        res = requests.get(
            f"{EDINET_BASE}/screener",
            params={**params, "limit": 1000},
            headers=EDINET_HEADERS,
            timeout=15,
        )
        if not res.ok:
            detail = res.text[:300].replace("\n", " ")
            raise RuntimeError(
                f"EDINET DB スクリーニング失敗: "
                f"{res.status_code} {res.reason} ({detail})"
            )
    except requests.RequestException as e:
        raise RuntimeError(f"EDINET DB スクリーニング失敗: {e}") from e

    candidates = res.json()["data"]["companies"]
    stats["candidates"] = len(candidates)

    if not candidates:
        return [], stats

    pending: list[dict] = []

    with get_db() as conn:
        init_db(conn)

        for i, co in enumerate(candidates, 1):
            edinet_code = co.get("edinetCode")
            name        = co.get("filerName", "不明")
            sec_code    = co.get("secCode", "")
            sec_code4   = sec_code[:4] if sec_code else ""

            if progress_cb:
                progress_cb(i, len(candidates), f"[{i}/{len(candidates)}] {name}")

            if not edinet_code or not sec_code4:
                stats["skipped"] += 1
                continue

            # 財務データ: DBキャッシュ優先
            cached = get_cached_financials(conn, edinet_code)
            if cached:
                latest = cached
                stats["cache_hit"] += 1
            else:
                try:
                    r = requests.get(
                        f"{EDINET_BASE}/companies/{edinet_code}/financials",
                        params={"years": 1},
                        headers=EDINET_HEADERS,
                        timeout=10,
                    )
                    r.raise_for_status()
                except requests.RequestException:
                    stats["skipped"] += 1
                    time.sleep(API_INTERVAL)
                    continue

                fin_data = r.json().get("data", [])
                if not fin_data:
                    stats["skipped"] += 1
                    time.sleep(API_INTERVAL)
                    continue

                latest = fin_data[-1]
                save_financials_cache(conn, edinet_code, name, sec_code4, latest)
                time.sleep(API_INTERVAL)

            current_assets    = latest.get("current_assets")
            total_liabilities = latest.get("total_liabilities")
            roa               = latest.get("roa")
            equity_ratio      = (
                latest.get("equity_ratio_official") or latest.get("equity_ratio")
            )
            fiscal_year = _to_int(co.get("fiscalYear") or latest.get("fiscal_year"))
            per_rt = _to_float(co.get("per"))
            pbr_rt = _to_float(co.get("pbr"))
            market_cap_million = _to_float(co.get("market-cap"))
            mktcap_oku = round(market_cap_million / 100, 1) if market_cap_million else None

            if current_assets is None or total_liabilities is None:
                stats["skipped"] += 1
                continue

            # ステップ2: 流動資産 > 負債合計
            if current_assets <= total_liabilities:
                continue

            # ステップ3: EDINET DBスクリーナー値でフィルタ
            gap_oku    = round((current_assets - total_liabilities) / 1e8, 1)
            net_cash_ratio = (
                round(gap_oku / mktcap_oku * 100, 1)
                if mktcap_oku and mktcap_oku > 0
                else None
            )

            if per_rt     is None or per_rt     > per_max:        continue
            if pbr_rt     is None or pbr_rt     > pbr_max:        continue
            if mktcap_oku is None or mktcap_oku > market_cap_max: continue
            if net_cash_ratio is None or net_cash_ratio < net_cash_ratio_min: continue

            close_price = get_latest_close(sec_code4) if JQUANTS_KEY else None

            pending.append({
                "run_date":          run_date,
                "sec_code":          sec_code4,
                "name":              name,
                "fiscal_year":       fiscal_year,
                "close_price":       close_price,
                "current_assets":    round(current_assets    / 1e8, 1),
                "total_liabilities": round(total_liabilities / 1e8, 1),
                "gap_oku":           gap_oku,
                "roa":               roa,
                "equity_ratio":      equity_ratio,
                "per":               per_rt,
                "pbr":               pbr_rt,
                "market_cap_oku":    mktcap_oku,
                "net_cash_ratio":    net_cash_ratio,
            })

        # 一括INSERT & commit
        if pending:
            conn.executemany(
                """
                INSERT INTO screening_results (
                    run_date, sec_code, name, fiscal_year,
                    close_price, current_assets, total_liabilities, gap_oku,
                    roa, equity_ratio, per, pbr, market_cap_oku, net_cash_ratio
                ) VALUES (
                    %(run_date)s, %(sec_code)s, %(name)s, %(fiscal_year)s,
                    %(close_price)s, %(current_assets)s, %(total_liabilities)s, %(gap_oku)s,
                    %(roa)s, %(equity_ratio)s, %(per)s, %(pbr)s, %(market_cap_oku)s, %(net_cash_ratio)s
                )
                """,
                pending,
            )
        conn.commit()

    pending.sort(key=lambda x: x["net_cash_ratio"] or 0, reverse=True)
    return pending, stats


# ================================================================
# 履歴クエリ（Streamlit / CLI 共通）
# ================================================================

def get_run_summary() -> list[dict]:
    """実行日ごとのヒット数サマリーを返す（直近20回）。"""
    with get_db() as conn:
        init_db(conn)
        rows = conn.execute(
            """
            SELECT run_date, COUNT(*) as count
            FROM screening_results
            GROUP BY run_date
            ORDER BY run_date DESC
            LIMIT 20
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_results_by_date(run_date: str) -> list[dict]:
    """指定日のスクリーニング結果を返す。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM screening_results WHERE run_date = %s ORDER BY net_cash_ratio DESC",
            (run_date,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stock_history(sec_code: str) -> list[dict]:
    """特定銘柄の出現履歴を返す。"""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT run_date, name, close_price, per, pbr, gap_oku, market_cap_oku, net_cash_ratio
            FROM screening_results
            WHERE sec_code = %s
            ORDER BY run_date DESC
            """,
            (sec_code,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_streak_ranking(min_hits: int = 1) -> list[dict]:
    """累計N回以上ヒットした銘柄と連続ヒット数を返す。"""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT sec_code, name, run_date
            FROM screening_results
            ORDER BY sec_code, run_date DESC
            """
        ).fetchall()
        all_dates = [
            _date_iso(r["run_date"])
            for r in conn.execute(
                "SELECT DISTINCT run_date FROM screening_results ORDER BY run_date DESC"
            ).fetchall()
        ]

    stock_dates: dict[str, list] = defaultdict(list)
    stock_names: dict[str, str]  = {}
    for row in rows:
        stock_dates[row["sec_code"]].append(_date_iso(row["run_date"]))
        stock_names[row["sec_code"]] = row["name"]

    results = []
    for code, run_dates in stock_dates.items():
        total = len(run_dates)
        if total < min_hits:
            continue
        streak = sum(1 for d in all_dates if d in run_dates)  # 連続ヒット数
        results.append({
            "sec_code":  code,
            "name":      stock_names[code],
            "total":     total,
            "streak":    streak,
            "first_hit": min(run_dates),
            "last_hit":  max(run_dates),
        })

    results.sort(key=lambda x: (-x["total"], -x["streak"]))
    return results


def get_all_results() -> list[dict]:
    """全履歴を返す。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM screening_results ORDER BY run_date DESC, net_cash_ratio DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ================================================================
# CSV エクスポート
# ================================================================

def _row_to_csv_list(row: dict) -> list:
    return [
        _date_iso(row["run_date"]),
        row["name"],
        row["sec_code"],
        row["fiscal_year"],
        row["close_price"] if row.get("close_price") is not None else "N/A",
        row["current_assets"],
        row["total_liabilities"],
        row["gap_oku"],
        row["net_cash_ratio"] if row.get("net_cash_ratio") is not None else "N/A",
        row["per"],
        row["pbr"],
        row["market_cap_oku"],
    ]


def export_csv_bytes(rows: list[dict]) -> bytes:
    """結果リストをCSVのバイト列（UTF-8 BOM付き）に変換する。Streamlitのダウンロードに使用。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for row in rows:
        writer.writerow(_row_to_csv_list(row))
    return buf.getvalue().encode("utf-8-sig")


def export_csv_file(rows: list[dict], filename: str) -> None:
    """結果リストをCSVファイルに書き出す。CLI用。"""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(_row_to_csv_list(row))
