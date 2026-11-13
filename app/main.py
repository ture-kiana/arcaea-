# -*- coding: utf-8 -*-
"""Arcaea b50 导出工具 —— 本地服务 + 内置网页界面"""
import base64, json, mimetypes, os, sys, threading, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api

STATE = {'result': None, 'pkg': api.PKGS['国服（韵律源点）'], 'serial': None}
CACHE = {}


def log_to(state):
    def _log(msg):
        state.setdefault('log', []).append(msg)
        print(msg, flush=True)
    return _log


class Handler(BaseHTTPRequestHandler):
    server_version = 'ArcaeaB50/1.0'

    def log_message(self, *a):
        pass

    # ── 工具 ──
    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _file(self, path, ctype=None):
        if not os.path.exists(path):
            return self._send(404, b'not found', 'text/plain')
        ctype = ctype or mimetypes.guess_type(path)[0] or 'application/octet-stream'
        with open(path, 'rb') as f:
            data = f.read()
        self._send(200, data, ctype)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(n) if n else b''

    # ── 路由 ──
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(p.path)
        qs = urllib.parse.parse_qs(p.query)

        if path in ('/', '/index.html'):
            return self._file(api.res('ui.html'), 'text/html; charset=utf-8')

        if path == '/api/status':
            return self._json(api.status())

        if path == '/api/state':
            return self._json({'result': STATE['result'], 'log': STATE.get('log', []),
                               'pkg': STATE['pkg']})

        if path == '/api/export-csv':
            if not STATE['result']:
                return self._json({'ok': False, 'message': '还没有数据'}, 400)
            d = api.workdir()
            return self._json({'ok': True, 'dir': os.path.join(d, 'data')})

        if path == '/api/quit':
            self._json({'ok': True})
            threading.Timer(0.4, lambda: os._exit(0)).start()
            return

        if path.startswith('/api/jacket/'):
            sid = path.rsplit('/', 1)[-1].replace('.jpg', '')
            return self._file(api.jacket_path(sid), 'image/jpeg')

        if path.startswith('/viewer'):
            return self._viewer(path, qs)

        return self._send(404, b'not found', 'text/plain')

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(p.path)
        try:
            body = json.loads(self._body() or b'{}')
        except Exception:
            body = {}

        if path == '/api/pull':
            return self._json(self.handle_pull(body.get('pkg') or STATE['pkg']))

        if path == '/api/upload':
            raw = body.get('data', '')
            if ',' in raw:
                raw = raw.split(',', 1)[1]
            try:
                blob = base64.b64decode(raw)
            except Exception as e:
                return self._json({'ok': False, 'message': f'文件读取失败：{e}'}, 400)
            return self._json(self.handle_blob(blob, '手动导入'))

        if path == '/api/jackets':
            return self._json(self.handle_jackets(body.get('count', 50)))

        return self._json({'ok': False, 'message': 'unknown'}, 404)

    # ── 业务 ──
    def handle_pull(self, pkg):
        st = {'log': []}
        log = log_to(st)
        pkg = api.PKGS.get(pkg, pkg)   # 界面传的是显示名，先映射成包名
        STATE['pkg'] = pkg
        log(f'目标包名：{pkg}')
        s = api.status()
        if not s.get('ok'):
            return {'ok': False, 'message': s.get('message', '连接失败'), 'log': st['log']}
        serial = s['device']['serial']
        STATE['serial'] = serial
        log(f"已连接：{s.get('model', '')}  Android {s.get('android', '')}")
        blob, err = api.pull_st3(serial, pkg, log=log)
        if not blob:
            return {'ok': False, 'message': err, 'log': st['log'], 'need_manual': True}
        return self.finish(blob, log, st['log'])

    def handle_blob(self, blob, source):
        st = {'log': []}
        log = log_to(st)
        log(f'来源：{source}')
        return self.finish(blob, log, st['log'])

    def finish(self, blob, log, logs):
        plays, missing = api.parse_st3(blob)
        if plays is None:
            return {'ok': False, 'message': '；'.join(missing), 'log': logs}
        log(f'读到 {len(plays)} 条成绩')
        if missing:
            log(f'{len(missing)} 个谱面缺定数（新曲未收录）：' + '、'.join(missing[:4]))
        summary = api.summarize(plays)
        hist = api.history(plays)
        api.write_csvs(plays, hist)
        log(f"PTT = ({summary['s50']:.3f} + {summary['s10']:.3f}) / 60 = {summary['ptt']:.3f}")
        STATE['result'] = {'summary': summary, 'hist': hist, 'log': logs}
        return {'ok': True, 'result': STATE['result'], 'log': logs}

    def handle_jackets(self, count):
        if not STATE['result']:
            return {'ok': False, 'message': '还没有数据'}
        serial = STATE['serial']
        if not serial:
            return {'ok': True, 'pulled': 0, 'note': '手动导入模式，曲绘用在线源兜底'}
        ids = [p['songId'] for p in STATE['result']['summary']['b50'][:int(count)]]
        ok = 0
        for sid in ids:
            if api.pull_jacket(serial, sid):
                ok += 1
        return {'ok': True, 'pulled': ok, 'total': len(ids)}

    def _viewer(self, path, qs):
        rel = path[len('/viewer'):].lstrip('/')
        if rel == '' or rel.startswith('index'):
            return self._file(api.res('viewer', 'index.html'), 'text/html; charset=utf-8')
        if rel in ('src/songs/songlist', 'src/songs/songlist.json'):
            return self._file(api.res('data', 'songlist'), 'application/json; charset=utf-8')
        if rel.startswith('data/'):
            return self._file(os.path.join(api.workdir(), rel), 'text/csv; charset=utf-8')
        if rel.startswith('src/songs/'):
            parts = rel.split('/')
            if len(parts) >= 4:
                return self._file(api.jacket_path(parts[2]), 'image/jpeg')
            return self._send(404, b'', 'text/plain')
        return self._file(api.res('viewer', rel))


def main():
    # --noconsole 打包后 sys.stdout 为 None，print 会崩，先兜住
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = sys.stdout
    port = 0
    for i, a in enumerate(sys.argv):
        if a == '--port' and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        if a == '--selftest':
            s = api.status()
            print('status:', json.dumps(s, ensure_ascii=False))
            if s.get('ok'):
                blob, err = api.pull_st3(s['device']['serial'], api.PKGS['国服（韵律源点）'])
                print('pull:', 'ok' if blob else err)
                if blob:
                    plays, missing = api.parse_st3(blob)
                    sm = api.summarize(plays)
                    print(f"PTT {sm['ptt']:.3f}  谱面 {sm['count']}  "
                          f"cut50 {sm['cut50']:.3f}")
            return

    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    port = httpd.server_address[1]
    url = f'http://127.0.0.1:{port}/'
    print(f'serving on {url}', flush=True)
    if '--no-browser' not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
