#!/usr/bin/env python3
import json, math, statistics, hashlib
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HIST = ROOT / 'data' / 'ssq_history.json'
OUT = ROOT / 'data' / 'daily_plan.json'
TODAY = date.today().isoformat()

hist = json.loads(HIST.read_text(encoding='utf-8'))
items = hist['items']
N = len(items)
red_counts = Counter()
blue_counts = Counter()
last_seen_r = {i: None for i in range(1,34)}
last_seen_b = {i: None for i in range(1,17)}
for idx, row in enumerate(items):  # items newest first; idx=0 means just appeared
    for r in row['red']:
        red_counts[r]+=1
        if last_seen_r[r] is None: last_seen_r[r]=idx
    b=row['blue']; blue_counts[b]+=1
    if last_seen_b[b] is None: last_seen_b[b]=idx

latest = items[0]
recent30 = items[:30]
recent60 = items[:60]
red30 = Counter(x for row in recent30 for x in row['red'])
red60 = Counter(x for row in recent60 for x in row['red'])
blue30 = Counter(row['blue'] for row in recent30)
blue60 = Counter(row['blue'] for row in recent60)

# 趋势分：不是预测，只是把“近期不太极端 + 长期有出现 + 有一定遗漏 + 避开上期”做成可解释排序。
red_scores = {}
for n in range(1,34):
    freq_all = red_counts[n] / max(1,N)                 # 长期出现率
    freq_30 = red30[n] / 30
    freq_60 = red60[n] / 60
    omit = last_seen_r[n] if last_seen_r[n] is not None else N
    zone_bonus = 0
    if n <= 11: zone_bonus = 0.4
    elif n <= 22: zone_bonus = 0.35
    else: zone_bonus = 0.45
    repeat_penalty = -1.2 if n in latest['red'] else 0
    hot_cold_balance = -abs(freq_30 - 6/33) * 4        # 不追极热极冷
    omit_score = min(omit, 18) / 18 * 1.4              # 温和遗漏
    red_scores[n] = round(freq_all*8 + freq_60*5 + hot_cold_balance + omit_score + zone_bonus + repeat_penalty, 4)

blue_scores = {}
for n in range(1,17):
    freq_all = blue_counts[n] / max(1,N)
    freq_30 = blue30[n] / 30
    freq_60 = blue60[n] / 60
    omit = last_seen_b[n] if last_seen_b[n] is not None else N
    repeat_penalty = -0.9 if n == latest['blue'] else 0
    hot_cold_balance = -abs(freq_30 - 1/16) * 3
    omit_score = min(omit, 12) / 12 * 1.2
    blue_scores[n] = round(freq_all*6 + freq_60*4 + hot_cold_balance + omit_score + repeat_penalty, 4)

# 当天固定 tie-breaker：同分时稳定，不随机刷新。
def stable_tiebreak(nums):
    h = hashlib.sha256((TODAY + '-' + ','.join(map(str, nums))).encode()).hexdigest()
    return int(h[:8], 16) / 1e10

def red_combo_score(nums):
    nums=tuple(sorted(nums))
    zones = [sum(1 for x in nums if x<=11), sum(1 for x in nums if 12<=x<=22), sum(1 for x in nums if x>=23)]
    odd = sum(x%2 for x in nums)
    total = sum(nums)
    span = max(nums)-min(nums)
    consec = sum(1 for a,b in zip(nums,nums[1:]) if b-a==1)
    # 结构约束：不要太偏区、太全奇偶、太连号、和值太极端。
    structure = 0
    structure -= sum(max(0,z-3)*1.0 for z in zones)
    structure -= abs(odd - len(nums)/2) * 0.35
    structure -= max(0, consec-1) * 0.8
    structure -= abs(total - len(nums)*17) / 35
    structure += min(span, 26) / 26 * 0.5
    return round(sum(red_scores[x] for x in nums) + structure + stable_tiebreak(nums), 5)

def best_red(n, require_disjoint=None):
    pool = range(1,34)
    if require_disjoint:
        pool = [x for x in pool if x not in require_disjoint]
    candidates=[]
    for nums in combinations(pool,n):
        z=[sum(1 for x in nums if x<=11),sum(1 for x in nums if 12<=x<=22),sum(1 for x in nums if x>=23)]
        if min(z)==0: continue
        if max(z)>4: continue
        odd=sum(x%2 for x in nums)
        if odd in (0,1,n-1,n): continue
        candidates.append((red_combo_score(nums), list(nums)))
    return max(candidates, key=lambda x:x[0])

def best_blue(n, require_disjoint=None):
    pool=[x for x in range(1,17) if not require_disjoint or x not in require_disjoint]
    candidates=[]
    for nums in combinations(pool,n):
        score=sum(blue_scores[x] for x in nums) - (max(nums)-min(nums)<4)*0.25 + stable_tiebreak(nums)
        candidates.append((round(score,5), list(nums)))
    return max(candidates, key=lambda x:x[0])

r1s,r1=best_red(7)
b1s,b1=best_blue(2)
r2s,r2=best_red(7, set(r1))
b2s,b2=best_blue(2, set(b1))
rj_s,rj=best_red(8)
bj_s,bj=best_blue(1)
rs_s,rs=best_red(7)
bs_s,bs=best_blue(4)

def fmt_plan(groups):
    return [{'red': g[0], 'blue': g[1], 'score': round(g[2],4)} for g in groups]

plan = {
  'date': TODAY,
  'fixed_for_day': True,
  'source': hist.get('source'),
  'history_count': hist.get('count'),
  'latest_issue': latest['code'],
  'latest_date': latest.get('date',''),
  'method': '固定日签名 + 最近120期热冷/遗漏/分区结构评分；同一天结果不会刷新。彩票独立随机，统计只用于结构优化，不保证中奖。',
  'recommended': 'balanced',
  'strategies': {
    'balanced': fmt_plan([(r1,b1,r1s+b1s),(r2,b2,r2s+b2s)]),
    'jackpot': fmt_plan([(rj,bj,rj_s+bj_s)]),
    'small': fmt_plan([(rs,bs,rs_s+bs_s)]),
  },
  'stats': {
    'red_hot': red_counts.most_common(6),
    'red_cold': sorted([(n, red_counts[n]) for n in range(1,34)], key=lambda x:x[1])[:6],
    'blue_hot': blue_counts.most_common(4),
    'blue_cold': sorted([(n, blue_counts[n]) for n in range(1,17)], key=lambda x:x[1])[:4],
    'red_top_score': sorted(red_scores.items(), key=lambda x:x[1], reverse=True)[:10],
    'blue_top_score': sorted(blue_scores.items(), key=lambda x:x[1], reverse=True)[:6],
  }
}
OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(plan, ensure_ascii=False, indent=2))
