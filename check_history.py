"""
check_history.py — 履歴確認CLIツール（screening.pyの関数を使用）

使い方:
  python check_history.py              # 実行サマリー
  python check_history.py --code 1234  # 特定銘柄の履歴
  python check_history.py --streak 3   # 3回以上ヒットした銘柄
  python check_history.py --all        # 全履歴をCSVエクスポート
"""

import argparse
from datetime import date

from screening import (
    export_csv_file,
    get_all_results,
    get_run_summary,
    get_stock_history,
    get_streak_ranking,
)


def cmd_summary() -> None:
    summary = get_run_summary()
    if not summary:
        print("まだスクリーニング結果がありません。")
        return
    print("=== 実行履歴サマリー（直近20回）===")
    print(f"{'日付':<14} {'ヒット数':>6}")
    print("-" * 22)
    for row in summary:
        print(f"  {row['run_date']:<14} {row['count']:>4}社")
    print(f"\n累計実行回数: {len(summary)}回")


def cmd_stock(sec_code: str) -> None:
    history = get_stock_history(sec_code)
    if not history:
        print(f"証券コード {sec_code} の履歴はありません。")
        return
    name = history[0].get("name", sec_code)
    print(f"=== {name}（{sec_code}）の履歴 ===")
    print(f"{'日付':<14} {'現在株価':>8} {'PER':>6} {'PBR':>5} {'差額':>8} {'時価総額':>8} {'NC比率':>8}")
    print("-" * 70)
    for r in history:
        net_cash_ratio = r.get("net_cash_ratio")
        net_cash_text = f"{net_cash_ratio}%" if net_cash_ratio is not None else "N/A"
        close_price = r.get("close_price")
        close_price_text = f"{close_price:,.0f}円" if close_price is not None else "N/A"
        print(
            f"  {r['run_date']:<14} "
            f"{close_price_text:>8} "
            f"{str(r['per']) + '倍':>6} "
            f"{str(r['pbr']) + '倍':>5} "
            f"{str(r['gap_oku']) + '億':>7} "
            f"{str(r['market_cap_oku']) + '億':>7} "
            f"{net_cash_text:>8}"
        )
    print(f"\n合計 {len(history)}回ヒット")


def cmd_streak(min_hits: int) -> None:
    results = get_streak_ranking(min_hits)
    print(f"=== {min_hits}回以上ヒットした銘柄 ===")
    if not results:
        print("該当銘柄なし")
        return
    print(f"{'社名':<20} {'コード'} {'累計':>4} {'連続':>6} {'初回':>12} {'最終':>12}")
    print("-" * 65)
    for r in results:
        print(
            f"  {r['name']:<20} {r['sec_code']:<5} "
            f"{r['total']:>3}回 "
            f"{r['streak']:>5}回連続 "
            f"{r['first_hit']:>12} "
            f"{r['last_hit']:>12}"
        )


def cmd_export_all() -> None:
    rows = get_all_results()
    filename = f"screening_all_{date.today().isoformat()}.csv"
    export_csv_file(rows, filename)
    print(f"✓ 全履歴CSVを出力しました: {filename}（{len(rows)}件）")


def main() -> None:
    parser = argparse.ArgumentParser(description="スクリーニング履歴確認ツール", epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--code",   type=str, metavar="CODE", help="特定銘柄の履歴（4桁）")
    parser.add_argument("--streak", type=int, metavar="N",    help="N回以上ヒットした銘柄")
    parser.add_argument("--all",    action="store_true",       help="全履歴をCSVエクスポート")
    args = parser.parse_args()

    if args.code:
        cmd_stock(args.code)
    elif args.streak:
        cmd_streak(args.streak)
    elif args.all:
        cmd_export_all()
    else:
        cmd_summary()


if __name__ == "__main__":
    main()
