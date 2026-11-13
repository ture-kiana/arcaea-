# -*- coding: utf-8 -*-
"""Arcaea 国服 b50 工具 —— 核心逻辑（无 GUI，被 main.py 调用）"""
import csv, datetime, json, os, re, shutil, sqlite3, subprocess, sys, tempfile

BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.dirname(os.path.abspath(__file__))

PKGS = {
    '国服（韵律源点）': 'com.xd.arcaea.tapcn',
    '国际服（Arcaea）': 'moe.low.arc',
}
DIFF_NAME = {0: 'PST', 1: 'PRS', 2: 'FTR', 3: 'BYD', 4: 'ETR'}
DIFF_COLOR = {'PST': '#5a96dc', 'PRS': '#5fc878', 'FTR': '#b064e8',
              'BYD': '#de5858', 'ETR': '#8c96af'}
CLEAR_NAME = {0: 'TL', 1: 'NC', 2: 'FR', 3: 'PM', 4: 'EC', 5: 'HC'}

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


# ── 路径 ──────────────────────────────────────────────
def res(*parts):
    return os.path.join(BASE, *parts)


def workdir():
    root = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(root, 'ArcaeaB50')
    for sub in ('', 'jackets', 'data', 'cache'):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def adb_path():
    for cand in (res('tools', 'adb.exe'), res('platform-tools', 'adb.exe')):
        if os.path.exists(cand):
            return cand
    return shutil.which('adb') or 'adb'


# ── adb ───────────────────────────────────────────────
def run(args, timeout=25):
    cmd = [adb_path()] + args
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        return p.returncode, p.stdout.decode('utf-8', 'ignore'), p.stderr.decode('utf-8', 'ignore')
    except FileNotFoundError:
        return 127, '', 'adb not found'
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout'


def status():
    """返回连接状态，供界面显示"""
    code, out, err = run(['start-server'], timeout=20)
    if code == 127:
        return {'ok': False, 'reason': 'missing_adb',
                'message': 'adb 未找到（安装包损坏或被杀软隔离）'}
    code, out, _ = run(['devices', '-l'])
    lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith('List of')]
    devices = []
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = ''
        m = re.search(r'model:(\S+)', line)
        if m:
            model = m.group(1).replace('_', ' ')
        devices.append({'serial': serial, 'state': state, 'model': model})
    if not devices:
        return {'ok': False, 'reason': 'no_device',
                'message': '没有检测到手机。检查数据线（要能传数据）、USB 调试是否打开、通知栏是否选了「传输文件」'}
    d = devices[0]
    if d['state'] == 'unauthorized':
        return {'ok': False, 'reason': 'unauthorized', 'device': d,
                'message': '手机还没授权。看手机屏幕，弹窗里勾「一律允许」再点允许'}
    if d['state'] != 'device':
        return {'ok': False, 'reason': d['state'], 'device': d,
                'message': f'设备状态异常：{d["state"]}'}
    # 设备就绪，读一下机型/系统
    info = {'ok': True, 'device': d}
    code, out, _ = run(['-s', d['serial'], 'shell',
                        'getprop ro.product.model; getprop ro.build.version.release'], timeout=15)
    if code == 0:
        vals = [l.strip() for l in out.splitlines() if l.strip()]
        info['model'] = vals[0] if vals else d['model']
        info['android'] = vals[1] if len(vals) > 1 else ''
    return info


def pkg_installed(serial, pkg):
    code, out, _ = run(['-s', serial, 'shell', f'pm path {pkg}'], timeout=15)
    return code == 0 and 'package:' in out


# ── 拉取 st3 ──────────────────────────────────────────
def adb_bytes(args, timeout=90):
    """按二进制取 adb 输出（存档是 SQLite，不能过文本解码）"""
    try:
        p = subprocess.run([adb_path()] + args, capture_output=True,
                           timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return p.returncode, p.stdout, p.stderr.decode('utf-8', 'ignore')
    except FileNotFoundError:
        return 127, b'', 'adb not found'
    except subprocess.TimeoutExpired:
        return 124, b'', 'timeout'


def pull_st3(serial, pkg, log=print):
    """三种方式依次尝试：run-as / root / 直接读"""
    remote = f'/data/data/{pkg}/files/st3'
    log(f'目标包名：{pkg}')
    if not pkg_installed(serial, pkg):
        return None, f'这台手机上没装 {pkg}'

    log('尝试 run-as（debuggable 构建，无需 root）…')
    code, out, err = adb_bytes(['-s', serial, 'exec-out', f'run-as {pkg} cat files/st3'])
    if code == 0 and out.startswith(b'SQLite format'):
        log('run-as 成功')
        return out, None
    if err.strip():
        log(f'  run-as 返回：{err.strip()[:120]}')

    log('尝试 root…')
    code, out, err = adb_bytes(['-s', serial, 'exec-out', f'su -c cat {remote}'], timeout=60)
    if code == 0 and out.startswith(b'SQLite format'):
        log('root 成功')
        return out, None

    return None, ('读不到存档。这个包不是 debuggable 构建且手机没有 root。\n'
                  '可以点「手动选择 st3 文件」导入（获取方式见教程最后一节）。')


# ── 解析与计算 ────────────────────────────────────────
def load_meta():
    songs = {s['id']: s for s in json.load(open(res('data', 'songlist'), encoding='utf-8'))['songs']}
    consts = json.load(open(res('data', 'constants.json'), encoding='utf-8'))['songConstants']
    return songs, consts


def single_ptt(const, score, clear_type):
    base = (const + 2 if score >= 10000000
            else const + 1 + (score - 9800000) / 200000 if score >= 9800000
            else max(0.0, const + (score - 9500000) / 300000))
    return base + (0.2 if clear_type != 0 else 0.0)


def parse_st3(blob):
    """blob: st3 文件字节。返回 (plays, missing)"""
    tmp = os.path.join(workdir(), 'cache', 'st3.db')
    with open(tmp, 'wb') as f:
        f.write(blob)
    songs, consts = load_meta()
    con = sqlite3.connect(tmp)
    try:
        clears = {(a, b): c for a, b, c in
                  con.execute('select songId,songDifficulty,clearType from cleartypes')}
        rows = con.execute('select songId,songDifficulty,score,shinyPerfectCount,perfectCount,'
                           'nearCount,missCount,date from scores').fetchall()
    except sqlite3.DatabaseError as e:
        return None, [f'存档格式无法识别：{e}']
    plays, missing = [], []
    for sid, diff, score, shiny, perfect, near, miss, date in rows:
        song = songs.get(sid)
        const = consts.get(str(song['idx']), {}).get(DIFF_NAME.get(diff, '')) if song else None
        title = (song.get('title_localized') or {}).get('en', sid) if song else sid
        if const is None:
            missing.append(f'{sid} [{DIFF_NAME.get(diff, diff)}]')
            continue
        pure = (shiny or 0) + (perfect or 0)
        far, lost = near or 0, miss or 0
        plays.append({
            'songId': sid, 'title': title, 'diff': diff, 'diffName': DIFF_NAME.get(diff, '?'),
            'const': const, 'score': score, 'pure': pure, 'far': far, 'lost': lost,
            'maxPure': pure + far + lost, 'ct': clears.get((sid, diff), 1),
            'ctName': CLEAR_NAME.get(clears.get((sid, diff), 1), 'NC'),
            'ts': int(date or 0) * 1000,
            'ptt': single_ptt(const, score, clears.get((sid, diff), 1)),
        })
    con.close()
    plays.sort(key=lambda p: -p['ptt'])
    return plays, missing


def level_label(c):
    ip = int(c)
    return f'{ip}+' if ip >= 7 and round(c - ip + 1e-9, 1) >= 0.7 else str(ip)


def summarize(plays):
    b50, b10 = plays[:50], plays[:10]
    s50 = sum(p['ptt'] for p in b50)
    s10 = sum(p['ptt'] for p in b10)
    total = (s50 + s10) / 60 if plays else 0
    for p in plays:
        p['level'] = level_label(p['const'])
        p['color'] = DIFF_COLOR.get(p['diffName'], '#888')
    return {
        'ptt': total, 's50': s50, 's10': s10,
        'count': len(plays), 'b50': b50, 'b10': b10,
        'avg50': s50 / max(1, len(b50)),
        'avg10': s10 / max(1, min(10, len(b10))),
        'cut50': b50[-1]['ptt'] if b50 else 0,
        'cut10': b10[-1]['ptt'] if b10 else 0,
        'maxPtt': (s50 + s10) / 60 if plays else 0,
    }


def history(plays):
    """按时间回放，得到阶梯 PTT 曲线"""
    seen, curve = {}, []
    for ts in sorted({p['ts'] for p in plays if p['ts']}):
        for p in plays:
            if p['ts'] == ts:
                seen[(p['songId'], p['diff'])] = p
        best = sorted(seen.values(), key=lambda x: -x['ptt'])[:50]
        s50 = sum(b['ptt'] for b in best)
        s10 = sum(b['ptt'] for b in best[:10])
        curve.append({'ts': ts, 'ptt': (s50 + s10) / 60})
    return curve


# ── 曲绘 ──────────────────────────────────────────────
def jacket_path(song_id):
    return os.path.join(workdir(), 'jackets', song_id + '.jpg')


def pull_jacket(serial, song_id, log=None):
    out = jacket_path(song_id)
    if os.path.exists(out) and os.path.getsize(out) > 800:
        return True
    base = f'/data/data'
    for pkg in PKGS.values():
        for dn in (song_id, 'dl_' + song_id):
            for fn in ('1080_base_256.jpg', 'base_256.jpg', '1080_base.jpg'):
                try:
                    p = subprocess.run(
                        [adb_path(), '-s', serial, 'exec-out',
                         f'run-as {pkg} cat files/cb/active/songs/{dn}/{fn}'],
                        capture_output=True, timeout=40, creationflags=CREATE_NO_WINDOW)
                    if p.returncode == 0 and len(p.stdout) > 800 and p.stdout[:2] == b'\xff\xd8':
                        open(out, 'wb').write(p.stdout)
                        return True
                except Exception:
                    continue
    if log:
        log(f'  曲绘缺失：{song_id}')
    return False


# ── 导出 CSV（给完整查看器用）──────────────────────────
def write_csvs(plays, hist):
    d = os.path.join(workdir(), 'data')
    with open(os.path.join(d, 'all_scores.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['SongId', 'Difficulty', 'Score', 'Constant', 'Potential', 'LS',
                    'MaxPure', 'Pure', 'Far', 'Lost', 'ClearType', 'Timestamp', 'DateTime'])
        for p in plays:
            dt = datetime.datetime.fromtimestamp(p['ts'] / 1000).strftime('%Y-%m-%d %H:%M:%S') if p['ts'] else ''
            w.writerow([p['songId'], p['diff'], p['score'], f"{p['const']:.1f}",
                        f"{p['ptt']:.5f}", 0, p['maxPure'], p['pure'], p['far'],
                        p['lost'], p['ct'], p['ts'], dt])
    with open(os.path.join(d, 'ratings.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Timestamp', 'DateTime', 'UserRating'])
        for point in hist:
            dt = datetime.datetime.fromtimestamp(point['ts'] / 1000).strftime('%Y/%m/%d %H:%M')
            w.writerow([point['ts'], dt, f"{point['ptt']:.3f}"])
    return d
