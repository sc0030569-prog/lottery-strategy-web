#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mod_path = ROOT / 'generate_daily_plan.py'
spec = importlib.util.spec_from_file_location('generate_daily_plan_under_test', mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    data = json.loads((ROOT / 'data' / 'all_daily_plans.json').read_text(encoding='utf-8'))
    assert_true(data.get('draw_fetch'), 'all_daily_plans 缺少 draw_fetch 抓取元信息')
    assert_true('last_draws' in data and isinstance(data['last_draws'], list), '缺少昨日/最近开奖列表')
    assert_true(len(data['last_draws']) >= 5, '最近开奖列表数量不足')
    draw_by_id = {d['id']: d for d in data['last_draws']}
    for game in data['games']:
        if game['id'] in ('jczq', 'scratch'):
            continue
        assert_true(game.get('current_issue'), f"{game['name']} 缺少本期推荐期号")
        assert_true(game.get('draw_time'), f"{game['name']} 缺少本期开奖时间")
        assert_true(game.get('last_draw'), f"{game['name']} 缺少最近开奖")
        assert_true(game['id'] in draw_by_id, f"开奖列表缺少 {game['name']}")
        for play in game.get('plays', []):
            for ticket in play.get('tickets', []):
                assert_true(ticket.get('issue') == game['current_issue'], f"{game['name']} 选注缺少或期号不一致")
                assert_true(ticket.get('draw_time') == game['draw_time'], f"{game['name']} 选注缺少或开奖时间不一致")
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    for marker in ['开奖记录', '往期开奖记录', 'renderDraws', '期号', '开奖时间']:
        assert_true(marker in html, f'页面缺少标记: {marker}')
    print('ok')


if __name__ == '__main__':
    main()
