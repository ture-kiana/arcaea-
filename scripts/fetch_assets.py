# -*- coding: utf-8 -*-
"""拉取构建所需的第三方资源

曲目表 / 定数：smartrte 的 Arcaea 查分工具（静态资源）
分析页静态文件：Arctan01/arcaea-trend-b30

用法： python scripts/fetch_assets.py
"""
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'Mozilla/5.0'}

SONG_DATA = [
    ('https://smartrte.github.io/json/songlist', 'app/data/songlist'),
    ('https://smartrte.github.io/json/constants.json', 'app/data/constants.json'),
]

VIEWER_RAW = 'https://raw.githubusercontent.com/Arctan01/arcaea-trend-b30/main/'
VIEWER_FILES = [
    ('index.html', 'app/viewer/index.html'),
    ('rating.js', 'app/viewer/rating.js'),
    ('canvas-style.js', 'app/viewer/canvas-style.js'),
]
VIEWER_FONTS = [
    ('src/Fonts/Exo-Regular.ttf', 'app/viewer/src/Fonts/Exo-Regular.ttf'),
    ('src/Fonts/GeosansLight.ttf', 'app/viewer/src/Fonts/GeosansLight.ttf'),
    ('src/Fonts/L2-Regular.ttf', 'app/viewer/src/Fonts/L2-Regular.ttf'),
]


def grab(url, dest, min_size=500):
    path = os.path.join(ROOT, dest)
    if os.path.exists(path) and os.path.getsize(path) > min_size:
        print(f'  ✓ {dest}（已存在）')
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=UA)
        data = urllib.request.urlopen(req, timeout=45).read()
        if len(data) < min_size:
            raise ValueError(f'内容过小 {len(data)} 字节')
        with open(path, 'wb') as f:
            f.write(data)
        print(f'  ↓ {dest}  {len(data)/1024:.0f} KB')
        return True
    except Exception as e:
        print(f'  ✗ {dest}：{e}')
        return False


def main():
    print('曲目表 / 定数：')
    ok = all([grab(u, d) for u, d in SONG_DATA])

    print('分析页静态文件：')
    ok = all([grab(VIEWER_RAW + s, d) for s, d in VIEWER_FILES]) and ok

    print('分析页字体：')
    for s, d in VIEWER_FONTS:
        grab(VIEWER_RAW + s, d, min_size=10000)

    adb = os.path.join(ROOT, 'app', 'tools', 'adb.exe')
    print()
    if os.path.exists(adb):
        print('adb：已就位')
    else:
        print('adb：缺失！请把 Android platform-tools 中的 adb.exe / AdbWinApi.dll /')
        print('     AdbWinUsbApi.dll 复制到 app/tools/ 后再打包。')
        print('     下载：https://dl.google.com/android/repository/platform-tools-latest-windows.zip')

    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
