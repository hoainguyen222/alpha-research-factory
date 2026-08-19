#!/usr/bin/env bash
# Helper script to display the Quantitative Strategy Leaderboard from SQLite DB

cd "$(dirname "$0")"

python3 -c "
import sqlite3
import os

db_path = 'quant_platform.db'
if not os.path.exists(db_path):
    print('Database not found. Run scripts/auto_alpha_factory.py first!')
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

print('===================================================================================================')
print('                          HOAI_CODE QUANTITATIVE STRATEGY LEADERBOARD                              ')
print('===================================================================================================')
print(f'{\"Rank\":<5} | {\"Paper ID\":<26} | {\"Target\":<13} | {\"Sharpe\":<8} | {\"Max DD\":<8} | {\"Return\":<9} | {\"Win Rate\":<8}')
print('-'*99)

rows = list(c.execute('''
    SELECT paper_id, symbol, timeframe, sharpe_ratio, max_drawdown_pct, total_return_pct, hit_rate_pct 
    FROM backtest_metrics 
    ORDER BY sharpe_ratio DESC
'''))

if not rows:
    print('No backtest results recorded yet. Please drop a paper into inbox/ and run scripts/auto_alpha_factory.py')
else:
    for idx, row in enumerate(rows, 1):
        paper_id, symbol, tf, sharpe, max_dd, ret, win_rate = row
        target = f'{symbol} ({tf})'
        ret_str = f'+{ret:.1f}%' if ret >= 0 else f'{ret:.1f}%'
        print(f'#{idx:<4} | {paper_id:<26} | {target:<13} | {sharpe:<8.2f} | {max_dd:<7.1f}% | {ret_str:<9} | {win_rate:<7.1f}%')

print('===================================================================================================')
conn.close()
"
