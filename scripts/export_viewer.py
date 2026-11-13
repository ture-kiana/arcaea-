# -*- coding: utf-8 -*-
"""把 Arcaea 国服 st3 存档转成 arcaea-trend-b30 需要的两份 CSV。

输出：viewer/data/all_scores.csv、viewer/data/ratings.csv

字段对应关系：
  SongId/Difficulty/Score/Constant  ← scores 表
  Pure = shinyPerfect + perfect, Far = near, Lost = miss
  MaxPure = 该局物量（= Pure+Far+Lost，逐局精确）
  ClearType ← cleartypes 表（0=TL 1=NC 2=FR 3=PM 4=EC 5=HC）
  Timestamp ← scores.date（Unix 秒）
  LS（Loss Score）国服拿不到，固定 0；界面上建议关掉「显示 LS」

注意：st3 只保存每个谱面的**最佳**成绩及其达成时间，所以 PTT 曲线是
「每次刷新纪录」的阶梯曲线，不是逐局历史。这点和 Yurisaki Bot 的导出不同。
"""
import csv, datetime, json, os, shutil, sqlite3

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, 'arcaea-save', 'local_st3.db')
if not os.path.exists(DB):
    DB = os.path.join(ROOT, 'arcaea-save', 'st3_copy.db')
SONGLIST = os.path.join(ROOT, 'data', 'songlist')
CONSTANTS = os.path.join(ROOT, 'data', 'constants.json')
OUT_DIR = os.path.join(ROOT, 'viewer', 'data')

DT = {0: 'PST', 1: 'PRS', 2: 'FTR', 3: 'BYD', 4: 'ETR'}
DIFF_ID = {v: k for k, v in DT.items()}


def potential(score, constant, clear_type):
    base = (constant + 2 if score >= 10000000
            else constant + 1 + (score - 9800000) / 200000 if score >= 9800000
            else max(0.0, constant + (score - 9500000) / 300000))
    return base + (0.2 if clear_type != 0 else 0.0)


def load_meta():
    songs = {s['id']: s for s in json.load(open(SONGLIST, encoding='utf-8'))['songs']}
    consts = json.load(open(CONSTANTS, encoding='utf-8'))['songConstants']
    return songs, consts


def read_plays():
    songs, consts = load_meta()
    con = sqlite3.connect(DB)
    clears = {(a, b): c for a, b, c in
              con.execute('select songId,songDifficulty,clearType from cleartypes')}
    plays, missing = [], []
    q = ('select songId,songDifficulty,score,shinyPerfectCount,perfectCount,'
         'nearCount,missCount,date from scores')
    for sid, diff, score, shiny, perfect, near, miss, date in con.execute(q):
        song = songs.get(sid)
        const = consts.get(str(song['idx']), {}).get(DT.get(diff, '')) if song else None
        if const is None:
            missing.append((sid, DT.get(diff, diff)))
            continue
        ct = clears.get((sid, diff), 1)
        pure = (shiny or 0) + (perfect or 0)
        far, lost = near or 0, miss or 0
        plays.append({
            'songId': sid, 'diff': diff, 'score': score, 'constant': const,
            'potential': potential(score, const, ct), 'ls': 0,
            'maxPure': pure + far + lost, 'pure': pure, 'far': far, 'lost': lost,
            'clearType': ct, 'ts': int(date) * 1000,
        })
    plays.sort(key=lambda p: p['ts'])
    return plays, missing


def write_play_csv(plays, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['SongId', 'Difficulty', 'Score', 'Constant', 'Potential', 'LS',
                    'MaxPure', 'Pure', 'Far', 'Lost', 'ClearType', 'Timestamp', 'DateTime'])
        for p in plays:
            dt = datetime.datetime.fromtimestamp(p['ts'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            w.writerow([p['songId'], p['diff'], p['score'], p['constant'],
                        f"{p['potential']:.5f}", p['ls'], p['maxPure'], p['pure'],
                        p['far'], p['lost'], p['clearType'], p['ts'], dt])


def build_rating_history(plays):
    """按时间回放：每个时间点用当时的全部最佳成绩重算 PTT"""
    out = []
    seen = {}
    stamps = sorted({p['ts'] for p in plays})
    for ts in stamps:
        for p in plays:
            if p['ts'] == ts:
                seen[(p['songId'], p['diff'])] = p
        best = sorted(seen.values(), key=lambda x: -x['potential'])[:50]
        s50 = sum(b['potential'] for b in best)
        s10 = sum(b['potential'] for b in best[:10])
        out.append((ts, (s50 + s10) / 60, len(seen)))
    return out


def write_rating_csv(hist, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Timestamp', 'DateTime', 'UserRating'])
        for ts, rating, _ in hist:
            dt = datetime.datetime.fromtimestamp(ts / 1000).strftime('%Y/%m/%d %H:%M')
            w.writerow([ts, dt, f'{rating:.3f}'])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plays, missing = read_plays()
    write_play_csv(plays, os.path.join(OUT_DIR, 'all_scores.csv'))
    hist = build_rating_history(plays)
    write_rating_csv(hist, os.path.join(OUT_DIR, 'ratings.csv'))

    src = os.path.join(ROOT, 'viewer', 'src', 'songs')
    os.makedirs(src, exist_ok=True)
    shutil.copy(SONGLIST, os.path.join(src, 'songlist'))

    print(f'play 记录 {len(plays)} 条，缺定数 {len(missing)} 条')
    print(f'PTT 历史 {len(hist)} 个节点：{hist[0][1]:.2f} → {hist[-1][1]:.3f}')
    print('最新 PTT =', f'{hist[-1][1]:.3f}', '（共', hist[-1][2], '个谱面）')
    if missing:
        print('  缺定数：', missing[:5])


if __name__ == '__main__':
    main()
