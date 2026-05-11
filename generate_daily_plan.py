#!/usr/bin/env python3
import json, hashlib, random
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HIST = ROOT / 'data' / 'ssq_history.json'
OUT = ROOT / 'data' / 'daily_plan.json'
ALL_OUT = ROOT / 'data' / 'all_daily_plans.json'
TODAY = date.today().isoformat()


def stable_seed(*parts):
    h = hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()
    return int(h[:16], 16)


def stable_tiebreak(nums, salt=''):
    h = hashlib.sha256((TODAY + '-' + salt + '-' + ','.join(map(str, nums))).encode()).hexdigest()
    return int(h[:8], 16) / 1e10


def pad(n):
    return f'{int(n):02d}'


def deterministic_sample(pool, k, salt, avoid=None):
    avoid = set(avoid or [])
    nums = [x for x in pool if x not in avoid]
    rnd = random.Random(stable_seed(TODAY, salt))
    rnd.shuffle(nums)
    return sorted(nums[:k])


def deterministic_digits(k, salt):
    rnd = random.Random(stable_seed(TODAY, salt))
    return [rnd.randint(0, 9) for _ in range(k)]


def digit_sum(ds):
    return sum(int(x) for x in ds)


def span(ds):
    return max(ds) - min(ds)


def build_ssq():
    hist = json.loads(HIST.read_text(encoding='utf-8'))
    items = hist['items']
    N = len(items)
    red_counts = Counter()
    blue_counts = Counter()
    last_seen_r = {i: None for i in range(1,34)}
    last_seen_b = {i: None for i in range(1,17)}
    for idx, row in enumerate(items):
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

    red_scores = {}
    for n in range(1,34):
        freq_all = red_counts[n] / max(1,N)
        freq_30 = red30[n] / 30
        freq_60 = red60[n] / 60
        omit = last_seen_r[n] if last_seen_r[n] is not None else N
        zone_bonus = 0.4 if n <= 11 else (0.35 if n <= 22 else 0.45)
        repeat_penalty = -1.2 if n in latest['red'] else 0
        hot_cold_balance = -abs(freq_30 - 6/33) * 4
        omit_score = min(omit, 18) / 18 * 1.4
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

    def red_combo_score(nums):
        nums=tuple(sorted(nums))
        zones = [sum(1 for x in nums if x<=11), sum(1 for x in nums if 12<=x<=22), sum(1 for x in nums if x>=23)]
        odd = sum(x%2 for x in nums)
        total = sum(nums)
        span_v = max(nums)-min(nums)
        consec = sum(1 for a,b in zip(nums,nums[1:]) if b-a==1)
        structure = 0
        structure -= sum(max(0,z-3)*1.0 for z in zones)
        structure -= abs(odd - len(nums)/2) * 0.35
        structure -= max(0, consec-1) * 0.8
        structure -= abs(total - len(nums)*17) / 35
        structure += min(span_v, 26) / 26 * 0.5
        return round(sum(red_scores[x] for x in nums) + structure + stable_tiebreak(nums, 'ssq-red'), 5)

    def best_red(n, require_disjoint=None):
        pool = range(1,34)
        if require_disjoint:
            pool = [x for x in pool if x not in require_disjoint]
        candidates=[]
        for nums in combinations(pool,n):
            z=[sum(1 for x in nums if x<=11),sum(1 for x in nums if 12<=x<=22),sum(1 for x in nums if x>=23)]
            if min(z)==0 or max(z)>4: continue
            odd=sum(x%2 for x in nums)
            if odd in (0,1,n-1,n): continue
            candidates.append((red_combo_score(nums), list(nums)))
        return max(candidates, key=lambda x:x[0])

    def best_blue(n, require_disjoint=None):
        pool=[x for x in range(1,17) if not require_disjoint or x not in require_disjoint]
        candidates=[]
        for nums in combinations(pool,n):
            score=sum(blue_scores[x] for x in nums) - (max(nums)-min(nums)<4)*0.25 + stable_tiebreak(nums, 'ssq-blue')
            candidates.append((round(score,5), list(nums)))
        return max(candidates, key=lambda x:x[0])

    r1s,r1=best_red(7); b1s,b1=best_blue(2)
    r2s,r2=best_red(7, set(r1)); b2s,b2=best_blue(2, set(b1))
    rj_s,rj=best_red(8); bj_s,bj=best_blue(1)
    rs_s,rs=best_red(7); bs_s,bs=best_blue(4)

    def fmt_plan(groups):
        return [{'red': g[0], 'blue': g[1], 'score': round(g[2],4)} for g in groups]

    legacy_plan = {
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

    game = {
        'id':'ssq','name':'双色球','group':'福彩','budget':'56元','frequency':'每周二/四/日开奖',
        'desc':'红球33选6 + 蓝球16选1；当前主策略，偏大奖与覆盖平衡。',
        'risk':'历史统计只做结构评分，不保证中奖；固定56元，不倍投。',
        'method': legacy_plan['method'], 'latest_issue': latest['code'], 'latest_date': latest.get('date',''),
        'plays': [
            {'name':'主推均衡：两组7红2蓝','cost':'56元','bets':'28注','why':'两组红球尽量错开，蓝球覆盖4个，适合长期照买。', 'tickets': legacy_plan['strategies']['balanced']},
            {'name':'冲大奖：8红1蓝复式','cost':'56元','bets':'28注','why':'红球覆盖更强，适合只想冲一等奖/二等奖。', 'tickets': legacy_plan['strategies']['jackpot']},
            {'name':'多中小奖：7红4蓝复式','cost':'56元','bets':'28注','why':'蓝球覆盖更宽，小奖反馈更好。', 'tickets': legacy_plan['strategies']['small']},
        ],
        'stats': legacy_plan['stats']
    }
    return legacy_plan, game


def front_back_game(game_id, name, group, front_max, front_pick, back_max, back_pick, front_use, back_use, cost, bets, freq, desc):
    front = deterministic_sample(range(1, front_max+1), front_use, f'{game_id}-front')
    back = deterministic_sample(range(1, back_max+1), back_use, f'{game_id}-back')
    alt_front = deterministic_sample(range(1, front_max+1), front_pick, f'{game_id}-front-alt', avoid=front[:max(0, front_use-front_pick)])
    alt_back = deterministic_sample(range(1, back_max+1), back_pick, f'{game_id}-back-alt')
    return {
        'id':game_id,'name':name,'group':group,'budget':cost,'frequency':freq,'desc':desc,
        'risk':'每日固定号是结构覆盖模型，不代表提高真实开奖概率；不倍投。',
        'method':f'固定日签名 + 分区/奇偶/和值约束生成；同一天结果固定。',
        'plays':[
            {'name':f'主推复式：{front_use}前区{back_use}后区','cost':cost,'bets':bets,'why':'在固定预算内扩大前后区覆盖，适合照单执行。','tickets':[{'front':front,'back':back,'score':round(80+stable_tiebreak(front+back,game_id)*100,2)}]},
            {'name':'保守单式：1注备用','cost':'2元','bets':'1注','why':'如果当天只想轻仓，就只买这一注。','tickets':[{'front':alt_front,'back':alt_back,'score':round(70+stable_tiebreak(alt_front+alt_back,game_id+'alt')*100,2)}]},
        ]
    }


def qlc_game():
    nums = deterministic_sample(range(1,31), 8, 'qlc-main')
    single = deterministic_sample(range(1,31), 7, 'qlc-single')
    return {'id':'qlc','name':'七乐彩','group':'福彩','budget':'16元','frequency':'每周一/三/五开奖','desc':'30选7，无蓝球；比双色球简单，适合小预算红球覆盖。','risk':'不追冷号，不倍投。','method':'固定日签名 + 三区均衡 + 奇偶约束。','plays':[{'name':'主推：8码复式','cost':'16元','bets':'8注','why':'8个号覆盖7码组合，预算低、执行简单。','tickets':[{'nums':nums,'score':82}]},{'name':'轻仓：7码单式','cost':'2元','bets':'1注','why':'只想参与时用。','tickets':[{'nums':single,'score':70}]}]}


def kl8_game():
    ten = deterministic_sample(range(1,81), 10, 'kl8-select10')
    five = deterministic_sample(range(1,81), 5, 'kl8-select5')
    return {'id':'kl8','name':'快乐8','group':'福彩','budget':'12元','frequency':'每日开奖','desc':'80个号码开奖20个，玩法多；先只做小额固定组选，避免注数失控。','risk':'高频玩法容易追投，必须固定小额预算。','method':'固定日签名 + 低中高区间均衡。','plays':[{'name':'主推：选十1注','cost':'2元','bets':'1注','why':'覆盖面广但只买1注，防止越买越多。','tickets':[{'nums':ten,'score':76}]},{'name':'反馈型：选五5注','cost':'10元','bets':'5注','why':'5组小额分散，提升参与反馈但仍控制预算。','tickets':[{'nums':deterministic_sample(range(1,81),5,f"kl8-five-{i}"),'score':70+i} for i in range(1,6)]}]}


def digit_game(game_id, name, group, digits, budget, freq, desc):
    tickets=[]
    for i in range(1,4):
        ds=deterministic_digits(digits, f'{game_id}-{i}')
        tickets.append({'digits':ds,'sum':digit_sum(ds),'span':span(ds),'score':round(72+i*3+stable_tiebreak(ds,game_id+str(i))*100,2)})
    return {'id':game_id,'name':name,'group':group,'budget':budget,'frequency':freq,'desc':desc,'risk':'数字型也独立随机；直选/组选只是玩法不同，不保证命中。','method':'固定日签名 + 和值/跨度不过极端 + 奇偶形态分散。','plays':[{'name':f'主推：{digits}位直选3注','cost':budget,'bets':'3注','why':'三注形态分散：和值、跨度、奇偶不完全重复。','tickets':tickets}]}


def discipline_game(game_id, name, group, budget, freq, desc, rules):
    return {'id':game_id,'name':name,'group':group,'budget':budget,'frequency':freq,'desc':desc,'risk':'该类不适合用随机号码模型，页面只给每日固定纪律清单。','method':'固定日签名 + 预算纪律，不自动推荐具体比赛或刮刮乐彩票。','plays':[{'name':'今日固定纪律','cost':budget,'bets':'按清单执行','why':'避免冲动买、追买、临场加仓。','tickets':[{'rules':rules,'score':88}]}]}

legacy_ssq, ssq_game = build_ssq()
all_plans = {
    'date': TODAY,
    'fixed_for_day': True,
    'notice': '所有策略同一天固定，不刷新重抽；彩票独立随机，模型只做预算纪律和组合覆盖，不保证中奖。',
    'games': [
        ssq_game,
        digit_game('fc3d','福彩3D','福彩',3,'18元','每日开奖','000-999 三位数；适合做和值、跨度、组选/直选小额模型。'),
        qlc_game(),
        kl8_game(),
        front_back_game('dlt','大乐透','体彩',35,5,12,2,6,3,'54元','18注','每周一/三/六开奖','前区35选5 + 后区12选2；和双色球最接近，适合做复式固定号。'),
        digit_game('pl3','排列3','体彩',3,'18元','每日开奖','三位数字型，和福彩3D类似，适合小额固定策略。'),
        digit_game('pl5','排列5','体彩',5,'6元','每日开奖','五位数字型，难度更高，只做轻仓3注。'),
        digit_game('qxc','七星彩','体彩',7,'6元','每周二/五/日开奖','七位数字型，随机性强，只做轻仓娱乐。'),
        discipline_game('jczq','竞彩/胜负彩','体彩','≤50元','按赛事日','依赖比赛判断，不适合纯随机选号。', ['只选看得懂的比赛，不碰陌生联赛', '单日最多2-3场，不串太长', '赔率过低不买，临场冲动不加单', '赛前信息不完整就跳过']),
        discipline_game('scratch','即开票/刮刮乐','福彩/体彩','≤20元','到店即买','娱乐型即开票，不适合统计预测。', ['只买固定预算内几张', '不中不追加', '不按“差一点”继续追', '买完即停，当作娱乐消费']),
    ]
}

OUT.write_text(json.dumps(legacy_ssq, ensure_ascii=False, indent=2), encoding='utf-8')
ALL_OUT.write_text(json.dumps(all_plans, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(all_plans, ensure_ascii=False, indent=2))
