import struct, zlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TILES = os.path.join(ROOT, "tiles")
PREVIEW = os.path.join(ROOT, "preview.png")

import struct, zlib, os



def read_png(path):
    d = open(path, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n"
    i = 8
    ihdr = None
    plte = b""
    trns = b""
    idat = b""
    while i < len(d):
        ln = struct.unpack(">I", d[i:i + 4])[0]
        typ = d[i + 4:i + 8]
        body = d[i + 8:i + 8 + ln]
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        i += 12 + ln
    w, h, bd, ct, comp, filt, inter = ihdr
    assert inter == 0, "interlaced not supported"
    return w, h, bd, ct, plte, trns, zlib.decompress(idat)


def unfilter(w, h, bd, ct, raw):
    if ct == 3:
        bpp = 1
    elif ct == 2:
        bpp = 3
    elif ct == 6:
        bpp = 4
    else:
        raise ValueError("ct %s" % ct)
    stride = w * bpp
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif f == 3:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return bytes(out)


def to_rgba(path):
    w, h, bd, ct, plte, trns, raw = read_png(path)
    assert bd == 8
    px = unfilter(w, h, bd, ct, raw)
    rgba = bytearray(w * h * 4)
    if ct == 3:
        lut = []
        for k in range(256):
            if k * 3 + 2 < len(plte):
                a = trns[k] if k < len(trns) else 255
                lut.append((plte[k * 3], plte[k * 3 + 1], plte[k * 3 + 2], a))
            else:
                lut.append((0, 0, 0, 0))
        for n, idx in enumerate(px):
            r, g, b, a = lut[idx]
            o = n * 4
            rgba[o] = r
            rgba[o + 1] = g
            rgba[o + 2] = b
            rgba[o + 3] = a
    elif ct == 6:
        rgba[:] = px
    else:
        raise ValueError("ct %s" % ct)
    return w, h, bytes(rgba)


def write_png_rgba(path, w, h, rgba):
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    open(path, "wb").write(out)


# ---------- 1) 统一转真彩 RGBA ----------
names = ["%dm" % i for i in range(1, 10)] + ["%dp" % i for i in range(1, 10)] + \
        ["%ds" % i for i in range(1, 10)] + ["east", "south", "west", "north", "red", "green", "white", "back"]
cache = {}
for n in names:
    p = os.path.join(TILES, n + ".png")
    w, h, rgba = to_rgba(p)
    write_png_rgba(p, w, h, rgba)
    cache[n] = (w, h, rgba)
print("converted", len(names))

# ---------- 2) 合成 preview 480x320 ----------
PW, PH = 480, 320
buf = bytearray(PW * PH * 4)
# 毡面底色 + 轻微径向提亮
for y in range(PH):
    for x in range(PW):
        dx = (x - PW * 0.5) / (PW * 0.62)
        dy = (y - PH * 0.42) / (PH * 0.72)
        k = max(0.0, 1.0 - (dx * dx + dy * dy))
        r = int(10 + 18 * k)
        g = int(30 + 46 * k)
        b = int(22 + 32 * k)
        o = (y * PW + x) * 4
        buf[o] = r
        buf[o + 1] = g
        buf[o + 2] = b
        buf[o + 3] = 255


def blend(o, r, g, b, a):
    al = a / 255.0
    io = 1.0 - al
    buf[o] = int(buf[o] * io + r * al)
    buf[o + 1] = int(buf[o + 1] * io + g * al)
    buf[o + 2] = int(buf[o + 2] * io + b * al)
    buf[o + 3] = 255


def sample(src, sw, sh, sx, sy):
    x0 = int(sx)
    y0 = int(sy)
    fx = sx - x0
    fy = sy - y0
    x1 = min(x0 + 1, sw - 1)
    y1 = min(y0 + 1, sh - 1)

    def get(x, y):
        o = (y * sw + x) * 4
        return src[o], src[o + 1], src[o + 2], src[o + 3]

    p00, p10, p01, p11 = get(x0, y0), get(x1, y0), get(x0, y1), get(x1, y1)
    out = []
    for c in range(4):
        top = p00[c] * (1 - fx) + p10[c] * fx
        bot = p01[c] * (1 - fx) + p11[c] * fx
        out.append(int(top * (1 - fy) + bot * fy))
    return out


def draw_tile(name, dx, dy, dw, dh, shadow=True):
    sw, sh, src = cache[name]
    rad = 0
    if shadow:
        for yy in range(dy + 4, dy + dh + 12):
            for xx in range(dx - 4, dx + dw + 8):
                if 0 <= xx < PW and 0 <= yy < PH:
                    ddy = (yy - (dy + dh * 0.5)) / (dh * 0.62)
                    ddx = (xx - (dx + dw * 0.5)) / (dw * 0.72)
                    k = ddx * ddx + ddy * ddy
                    if k < 1.35:
                        a = int(120 * (1 - k / 1.35) ** 2)
                        if a > 0:
                            o = (yy * PW + xx) * 4
                            buf[o] = int(buf[o] * (1 - a / 255.0))
                            buf[o + 1] = int(buf[o + 1] * (1 - a / 255.0))
                            buf[o + 2] = int(buf[o + 2] * (1 - a / 255.0))
    for yy in range(dy, dy + dh):
        for xx in range(dx, dx + dw):
            if not (0 <= xx < PW and 0 <= yy < PH):
                continue
            # 圆角遮罩
            cx = min(max(xx - dx, 0), dw - 1)
            cy = min(max(yy - dy, 0), dh - 1)
            r = min(1.0, min(cx, dw - 1 - cx, cy, dh - 1 - cy) / float(rad)) if rad else 1.0
            if r <= 0:
                continue
            sx = (xx - dx) * sw / float(dw)
            sy = (yy - dy) * sh / float(dh)
            rr, gg, bb, aa = sample(src, sw, sh, sx, sy)
            aa = int(aa * min(1.0, r))
            if aa > 0:
                blend((yy * PW + xx) * 4, rr, gg, bb, aa)


TH = 130
TW = int(round(TH * 192 / 288.0))
gap = 8
rows = [["1m", "5m", "9m", "1p", "5p"],
        ["1s", "5s", "9s", "red", "back"]]
row_w = len(rows[0]) * TW + (len(rows[0]) - 1) * gap
x0 = (PW - row_w) // 2
block_h = len(rows) * TH + (len(rows) - 1) * gap
y0 = (PH - block_h) // 2 + 4
for ri, row in enumerate(rows):
    y = y0 + ri * (TH + gap)
    for ci, n in enumerate(row):
        draw_tile(n, x0 + ci * (TW + gap), y, TW, TH)

write_png_rgba(PREVIEW, PW, PH, bytes(buf))
print("preview", PW, PH, os.path.getsize(PREVIEW), "bytes")

# ---------- 3) 全量总览图 ----------
OVERVIEW = os.path.join(ROOT, "overview.png")
PW, PH = 1008, 672
buf = bytearray(PW * PH * 4)
for y in range(PH):
    for x in range(PW):
        o = (y * PW + x) * 4
        buf[o] = 10
        buf[o + 1] = 36
        buf[o + 2] = 25
        buf[o + 3] = 255

TW2, TH2, G2 = 96, 144, 12
rows2 = [[str(i) + "m" for i in range(1, 10)],
         [str(i) + "p" for i in range(1, 10)],
         [str(i) + "s" for i in range(1, 10)],
         ["east", "south", "west", "north", "red", "green", "white", "back"]]
sheet_w = 9 * TW2 + 8 * G2
sheet_h = len(rows2) * TH2 + (len(rows2) - 1) * 16
x0 = (PW - sheet_w) // 2
y0 = (PH - sheet_h) // 2
for ri, row in enumerate(rows2):
    for ci, n in enumerate(row):
        draw_tile(n, x0 + ci * (TW2 + G2), y0 + ri * (TH2 + 16), TW2, TH2)

write_png_rgba(OVERVIEW, PW, PH, bytes(buf))
print("overview", PW, PH, os.path.getsize(OVERVIEW), "bytes")
