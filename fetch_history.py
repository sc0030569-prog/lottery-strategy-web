#!/usr/bin/env python3
import json, re, time, urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'ssq_history.json'
OUT.parent.mkdir(parents=True, exist_ok=True)

def fetch_500(start='24001', end='26999'):
    url = f'https://datachart.500.com/ssq/history/newinc/history.php?start={start}&end={end}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://datachart.500.com/ssq/history/history.shtml',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode('gb2312', 'ignore')
    rows = []
    for tr in re.findall(r'<tr[^>]*?>(.*?)</tr>', html, flags=re.S|re.I):
        issue = re.search(r'<td>(\d{5})</td>', tr)
        reds = [int(x) for x in re.findall(r'class="t_cfont2">(\d{1,2})</td>', tr)]
        blue = re.search(r'class="t_cfont4">(\d{1,2})</td>', tr)
        date_match = re.search(r'(20\d{2}-\d{2}-\d{2})', tr)
        if issue and len(reds) >= 6 and blue:
            rows.append({'code': issue.group(1), 'date': date_match.group(1) if date_match else '', 'red': reds[:6], 'blue': int(blue.group(1))})
    rows.sort(key=lambda x: x['code'], reverse=True)
    return url, rows

source, items = fetch_500()
if len(items) < 50:
    raise SystemExit(f'开奖数据过少，疑似接口异常: {len(items)}')
OUT.write_text(json.dumps({
    'source': source,
    'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    'count': len(items),
    'items': items[:120],
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {OUT} count={len(items[:120])} latest={items[0]["code"]}')
