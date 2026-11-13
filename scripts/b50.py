# -*- coding: utf-8 -*-
"""一键更新：从手机拉取 st3 -> 计算 b50 -> 生成卡片
用法： python b50.py            （默认拉取并出图）
       python b50.py --no-pull  （只用已有的 local_st3.db 重算）
"""
import json, os, shutil, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ADB = os.path.join(ROOT, 'tools', 'platform-tools', 'adb.exe')
PKG = 'com.xd.arcaea.tapcn'
RAW = os.path.join(ROOT, 'arcaea-save', 'st3')
DB = os.path.join(ROOT, 'arcaea-save', 'local_st3.db')
SONGLIST = os.path.join(ROOT, 'data', 'songlist')
CONSTANTS = os.path.join(ROOT, 'data', 'constants.json')
OUTJSON = os.path.join(ROOT, 'arcaea-save', 'b50.json')

DT = {0: 'PST', 1: 'PRS', 2: 'FTR', 3: 'BYD', 4: 'ETR'}


JACKET_DIR = os.path.join(ROOT, 'data', 'jacket_off')
SONGS_PATH = f'/data/data/{PKG}/files/cb/active/songs'


def pull_jacket(song_id):
    """曲绘就在游戏本体：songs/<id>/1080_base.jpg；部分曲目目录带 dl_ 前缀、
    文件名退化为 base.jpg，两种都要试。"""
    out = os.path.join(JACKET_DIR, song_id + '.jpg')
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return True
    for dname in (song_id, 'dl_' + song_id):
        for fn in ('1080_base.jpg', 'base.jpg', '1080_base_256.jpg', 'base_256.jpg'):
            r = subprocess.run([ADB, 'exec-out',
                                f'run-as {PKG} cat {SONGS_PATH}/{dname}/{fn}'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if r.returncode == 0 and len(r.stdout) > 5000 and r.stdout[:2] == b'\xff\xd8':
                open(out, 'wb').write(r.stdout)
                return True
    return False


def pull_all_jackets(ids):
    os.makedirs(JACKET_DIR, exist_ok=True)
    miss = [i for i in ids if not pull_jacket(i)]
    print(f'曲绘 {len(ids) - len(miss)}/{len(ids)} 就绪' + (f'，缺 {miss}' if miss else ''))


def pull():
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    cmd = [ADB, 'exec-out', f'run-as {PKG} cat files/st3']
    with open(RAW, 'wb') as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
    if r.returncode != 0 or os.path.getsize(RAW) < 4096:
        sys.exit(f'拉取失败：{r.stderr.decode(errors="ignore")[:300]}')
    print(f'st3 已拉取 {os.path.getsize(RAW)} 字节')


def ptt(const, score, cleared):
    bonus = 0.0 if cleared == 0 else 0.2
    if score >= 10000000:
        return const + 2 + bonus
    if score >= 9800000:
        return const + 1 + (score - 9800000) / 200000 + bonus
    return max(0.0, const + (score - 9500000) / 300000 + bonus)


def compute():
    shutil.copy(RAW, DB)
    songs = {s['id']: s for s in json.load(open(SONGLIST, encoding='utf-8'))['songs']}
    consts = json.load(open(CONSTANTS, encoding='utf-8'))['songConstants']
    con = sqlite3.connect(DB)
    clears = {(a, b): c for a, b, c in
              con.execute('select songId,songDifficulty,clearType from cleartypes')}
    out, missing = [], []
    for sid, diff, score in con.execute('select songId,songDifficulty,score from scores'):
        song = songs.get(sid)
        c = consts.get(str(song['idx']), {}).get(DT.get(diff, '')) if song else None
        if c is None:
            missing.append((sid, DT.get(diff, diff), score))
            continue
        ct = clears.get((sid, diff), 1)
        out.append({'id': sid, 'name': (song.get('title_localized') or {}).get('en', sid),
                    'diff': DT.get(diff), 'const': c, 'score': score,
                    'ct': ct, 'ptt': ptt(c, score, ct)})
    out.sort(key=lambda x: -x['ptt'])
    b50, b10 = out[:50], out[:10]
    s50 = sum(x['ptt'] for x in b50)
    s10 = sum(x['ptt'] for x in b10)
    total = (s50 + s10) / 60
    json.dump({'top': b50, 'b10': b10, 'all': out, 'ptt': total, 's50': s50, 's10': s10},
              open(OUTJSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'谱面 {len(out)} 条，缺定数 {len(missing)} 条')
    if missing:
        for m in missing[:5]:
            print('  缺定数:', m)
    print(f'b50 总和 {s50:.3f}   b10 总和 {s10:.3f}')
    print(f'PTT = ({s50:.3f} + {s10:.3f}) / 60 = {total:.3f}')
    print(f'第50名 {b50[-1]["name"]} {b50[-1]["ptt"]:.3f}   '
          f'第10名 {b10[-1]["name"]} {b10[-1]["ptt"]:.3f}')
    return total


if __name__ == '__main__':
    if '--no-pull' not in sys.argv:
        pull()
    compute()
    pull_all_jackets([r['id'] for r in json.load(open(OUTJSON, encoding='utf-8'))['top']])
    subprocess.run([sys.executable, os.path.join(ROOT, 'render_card.py')], check=False)
    print('完成：arcaea-b50-card.png')
