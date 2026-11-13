# -*- coding: utf-8 -*-
"""按官方 b50 卡片版式渲染（5x10 网格）"""
import json, os, sqlite3, datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

B50 = 'arcaea-save/b50.json'
OUT = 'arcaea-b50-card.png'
JACKET = 'data/jacket_off'          # 游戏本体导出（1080 官方图）
JACKET_FALLBACK = 'data/jacket'     # 第三方站兜底
FB = 'C:/Windows/Fonts/msyhbd.ttc'
FR = 'C:/Windows/Fonts/msyh.ttc'
FN = 'C:/Windows/Fonts/ariblk.ttf'

DIFF_COLOR = {'PST': (90, 150, 220), 'PRS': (95, 200, 120), 'FTR': (176, 100, 232),
              'BYD': (222, 88, 88), 'ETR': (140, 150, 175)}
CLEAR_TXT = {3: 'PM', 2: 'FR', 1: 'C', 0: 'L', 4: 'EC', 5: 'HC'}

def level_label(c):
    """官方规则：定数整数部分 + 若小数 >=0.7 则标 '+'（9+ / 10+ / 11+）"""
    ip = int(c)
    frac = round(c - ip + 1e-9, 1)
    if ip >= 7 and frac >= 0.7:
        return f'{ip}+'
    return str(ip)


def f(path, size):
    return ImageFont.truetype(path, size)

def rounded(img, radius):
    m = Image.new('L', img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.size[0]-1, img.size[1]-1], radius, fill=255)
    return m

def bg(w, h):
    im = Image.new('RGB', (w, h), (10, 8, 16))
    d = ImageDraw.Draw(im)
    # 顶部/中部紫光
    glow = Image.new('RGB', (w, h), (10, 8, 16))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w*0.1, -h*0.25, w*1.1, h*0.55], fill=(46, 28, 78))
    gd.ellipse([-w*0.3, h*0.45, w*0.7, h*1.1], fill=(28, 20, 52))
    gd.ellipse([w*0.55, h*0.7, w*1.4, h*1.3], fill=(34, 22, 60))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(120)), 0.85)
    # 细网格
    ov = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for x in range(0, w, 26):
        od.line([(x, 0), (x, h)], fill=(255, 255, 255, 5))
    for y in range(0, h, 26):
        od.line([(0, y), (w, y)], fill=(255, 255, 255, 5))
    im = Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')
    return im

def text_w(d, s, fnt):
    b = d.textbbox((0, 0), s, font=fnt)
    return b[2]-b[0], b[3]-b[1]

def main():
    data = json.load(open(B50, encoding='utf-8'))
    top = data['top']
    ptt_total = data['ptt']

    W = 1080
    COLS, GAP, M = 5, 10, 24
    CW = (W - 2*M - GAP*(COLS-1)) // COLS      # 198
    JH = 152                                    # 曲绘高
    CH = JH + 62                                # 卡片总高
    HEAD = 210
    FOOT = 56
    ROWS = 10
    H = HEAD + ROWS*CH + (ROWS-1)*GAP + FOOT

    im = bg(W, H)
    d = ImageDraw.Draw(im, 'RGBA')

    f_logo = f(FN, 46)
    f_tag = f(FR, 13)
    f_gen_l = f(FR, 14)
    f_gen_v = f(FB, 22)
    f_title = f(FB, 20)
    f_ptt_big = f(FN, 58)
    f_rank = f(FB, 16)
    f_lvl = f(FB, 15)
    f_lvl_s = f(FB, 13)
    f_song = f(FB, 14)
    f_sp = f(FB, 18)
    f_sc = f(FR, 13)
    f_badge = f(FB, 12)
    f_foot = f(FR, 13)

    # ---- 头部 ----
    d.text((M, 34), 'Arcaea', font=f_logo, fill=(246, 242, 255))
    d.text((M+4, 92), 'RHYTHM  GAME', font=f_tag, fill=(168, 156, 200))
    d.text((M+4, 112), 'B E S T   5 0   +   1 0', font=f_tag, fill=(140, 128, 172))

    gw, _ = text_w(d, 'Generated on:', f_gen_l)
    d.text((W-M-gw, 40), 'Generated on:', font=f_gen_l, fill=(150, 140, 180))
    ds = datetime.date.today().strftime('%Y/%m/%d')
    dw, _ = text_w(d, ds, f_gen_v)
    d.text((W-M-dw, 58), ds, font=f_gen_v, fill=(240, 236, 255))

    # 中间 PTT
    label = 'POTENTIAL'
    lw, _ = text_w(d, label, f_tag)
    d.text(((W-lw)//2, 40), label, font=f_tag, fill=(150, 140, 180))
    pv = f'{ptt_total:.3f}'
    pw, ph = text_w(d, pv, f_ptt_big)
    px, py = (W-pw)//2, 64
    d.text((px+2, py+3), pv, font=f_ptt_big, fill=(20, 12, 40))
    d.text((px, py), pv, font=f_ptt_big, fill=(232, 226, 255))
    # 分隔光带
    d.line([(M, HEAD-46), (W-M, HEAD-46)], fill=(96, 84, 140, 120), width=1)
    d.line([(M, HEAD-8), (W-M, HEAD-8)], fill=(70, 60, 105, 90), width=1)

    # ---- 卡片 ----
    for i, r in enumerate(top[:50]):
        col, row = i % COLS, i // COLS
        x = M + col*(CW+GAP)
        y = HEAD + row*(CH+GAP)
        dc = DIFF_COLOR.get(r['diff'], (150, 150, 180))

        # 底板（b10 双倍权重用高亮描边区分）
        top10 = i < 10
        d.rounded_rectangle([x, y, x+CW, y+CH], 8, fill=(26, 22, 40, 255))
        if top10:
            d.rounded_rectangle([x, y, x+CW, y+CH], 8, outline=(186, 150, 255, 255), width=2)
        else:
            d.rounded_rectangle([x, y, x+CW, y+CH], 8, outline=(72, 62, 108, 255), width=1)

        # 曲绘
        jp = os.path.join(JACKET, r['id'] + '.jpg')
        if not os.path.exists(jp):
            jp = os.path.join(JACKET_FALLBACK, r['id'] + '.jpg')
        if os.path.exists(jp):
            j = Image.open(jp).convert('RGB')
            # 居中裁成卡片比例，避免拉伸
            tw, th = CW - 4, JH - 4
            sw, sh = j.size
            scale = max(tw / sw, th / sh)
            j = j.resize((max(1, int(sw * scale)), max(1, int(sh * scale))), Image.LANCZOS)
            left = (j.size[0] - tw) // 2
            crop_top = int((j.size[1] - th) * 0.32)
            j = j.crop((left, crop_top, left + tw, crop_top + th))
        else:
            j = Image.new('RGB', (CW - 4, JH - 4), (40, 34, 60))
        im.paste(j, (x+2, y+2), rounded(j, 6))

        # 曲绘底部渐隐
        fade = Image.new('L', (CW-4, 46), 0)
        fd = ImageDraw.Draw(fade)
        for k in range(46):
            fd.line([(0, k), (CW-4, k)], fill=int(200*(k/45)**1.6))
        im.paste((14, 11, 24), (x+2, y+JH-46), fade)

        # 编号
        d.rounded_rectangle([x+4, y+4, x+42, y+22], 4, fill=(12, 9, 20, 210))
        d.text((x+10, y+6), f'#{i+1}', font=f_rank, fill=(238, 232, 255))
        if top10:
            d.rounded_rectangle([x+44, y+4, x+74, y+22], 4, fill=(88, 64, 150, 235))
            d.text((x+49, y+6), '×2', font=f_badge, fill=(236, 226, 255))

        # 等级标注（9+ / 10+ …）
        lv = level_label(r['const'])
        f_lv = f_lvl if len(lv) <= 2 else f_lvl_s
        lw2, lh2 = text_w(d, lv, f_lv)
        pw2, ph2 = max(30, lw2 + 14), 30
        cx, cy = x+CW-6-pw2/2-4, y+20
        d.rounded_rectangle([cx-pw2/2, cy-ph2/2, cx+pw2/2, cy+ph2/2], ph2/2,
                            fill=(14, 11, 24, 232), outline=dc+(255,), width=2)
        d.text((cx-lw2/2, cy-lh2/2-2), lv, font=f_lv, fill=dc)

        # 曲名（超宽时自动缩字号，最后才截断）
        nm = r['name']
        maxw = CW - 14
        fnt = f_song
        for sz in (14, 13, 12, 11):
            fnt = f(FB, sz)
            if text_w(d, nm, fnt)[0] <= maxw:
                break
        while text_w(d, nm, fnt)[0] > maxw and len(nm) > 3:
            nm = nm[:-1]
        if nm != r['name']:
            nm = nm[:-1] + '…'
        d.text((x+6, y+JH+4), nm, font=fnt, fill=(232, 228, 246))

        # ptt + 分数
        d.text((x+6, y+JH+24), f"{r['ptt']:.3f}", font=f_sp, fill=(178, 224, 255))
        sc = f"{r['score']:,}"
        sw, _ = text_w(d, sc, f_sc)
        d.text((x+CW-6-sw, y+JH+29), sc, font=f_sc, fill=(196, 190, 214))

        # 通关标记
        ct = r.get('ct', 1)
        btxt = CLEAR_TXT.get(ct, 'C')
        bcol = (176, 100, 232) if ct == 3 else ((95, 200, 170) if ct == 2 else (150, 148, 170))
        bw, _ = text_w(d, btxt, f_badge)
        d.rounded_rectangle([x+CW-8-bw-10, y+JH+4, x+CW-6, y+JH+18], 3, fill=(30, 24, 46, 230), outline=bcol+(220,))
        d.text((x+CW-8-bw-5, y+JH+4), btxt, font=f_badge, fill=bcol)

    # ---- 页脚 ----
    fy = H-FOOT+14
    d.text((M, fy), '© lowiro', font=f_foot, fill=(140, 132, 170))
    avg = sum(r['ptt'] for r in top[:50])/max(1, len(top[:50]))
    note = f'(B50 + B10) / 60   ·   B50 sum {sum(r["ptt"] for r in top[:50]):.3f}   ·   st3 本地解析'
    nw, _ = text_w(d, note, f_foot)
    d.text((W-M-nw, fy), note, font=f_foot, fill=(120, 113, 150))

    im.save(OUT)
    print('saved', OUT, im.size)

if __name__ == '__main__':
    main()
