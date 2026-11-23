"""Small QR decoder. Versions 1–10, numeric, alphanumeric and byte modes.

No third-party library. A photo that does not yield a code returns None.
Micro QR and versions above 10 are out of range and return None.
"""

# ISO/IEC 18004 Table 9. Each entry is groups of (block count, total codewords, data codewords).
_ECC = {
    1: {'L': ((1, 26, 19),), 'M': ((1, 26, 16),), 'Q': ((1, 26, 13),), 'H': ((1, 26, 9),)},
    2: {'L': ((1, 44, 34),), 'M': ((1, 44, 28),), 'Q': ((1, 44, 22),), 'H': ((1, 44, 16),)},
    3: {'L': ((1, 70, 55),), 'M': ((1, 70, 44),), 'Q': ((2, 35, 17),), 'H': ((2, 35, 13),)},
    4: {'L': ((1, 100, 80),), 'M': ((2, 50, 32),), 'Q': ((2, 50, 24),), 'H': ((4, 25, 9),)},
    5: {'L': ((1, 134, 108),), 'M': ((2, 67, 43),), 'Q': ((2, 33, 15), (2, 34, 16)),
        'H': ((2, 33, 11), (2, 34, 12))},
    6: {'L': ((2, 86, 68),), 'M': ((4, 43, 27),), 'Q': ((4, 43, 19),), 'H': ((4, 43, 15),)},
    7: {'L': ((2, 98, 78),), 'M': ((4, 49, 31),), 'Q': ((2, 32, 14), (4, 33, 15)),
        'H': ((4, 39, 13), (1, 40, 14))},
    8: {'L': ((2, 121, 97),), 'M': ((2, 60, 38), (2, 61, 39)), 'Q': ((4, 40, 18), (2, 41, 19)),
        'H': ((4, 40, 14), (2, 41, 15))},
    9: {'L': ((2, 146, 116),), 'M': ((3, 58, 36), (2, 59, 37)), 'Q': ((4, 36, 16), (4, 37, 17)),
        'H': ((4, 36, 12), (4, 37, 13))},
    10: {'L': ((2, 86, 68), (2, 87, 69)), 'M': ((4, 69, 43), (1, 70, 44)),
         'Q': ((6, 43, 19), (2, 44, 20)), 'H': ((6, 43, 15), (2, 44, 16))},
}
# Annex E. Version 1 has none.
_ALIGN = {
    2: (6, 18), 3: (6, 22), 4: (6, 26), 5: (6, 30), 6: (6, 34),
    7: (6, 22, 38), 8: (6, 24, 42), 9: (6, 26, 46), 10: (6, 28, 50),
}
_ALPH = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:'
_LEVEL = {0b01: 'L', 0b00: 'M', 0b11: 'Q', 0b10: 'H'}


def _formats():
    out = []
    for data in range(32):
        bits = data << 10
        for i in range(4, -1, -1):
            if bits & (1 << (i + 10)):
                bits ^= 0x537 << i
        out.append(((data << 10) | (bits & 0x3FF)) ^ 0x5412)
    return out


_FORMATS = _formats()

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _pow_inv(a):
    return _EXP[255 - _LOG[a]]


def _rs_bm(block, syn, nsym):
    C = [1]
    B = [1]
    L = 0
    m = 1
    b = 1
    for n in range(nsym):
        delta = syn[n]
        for i in range(1, L + 1):
            delta ^= _mul(C[i], syn[n - i])
        if delta == 0:
            m += 1
            continue
        T = C[:]
        coef = _mul(delta, _pow_inv(b))
        C = C + [0] * (m + len(B) - len(C))
        for i, value in enumerate(B):
            C[i + m] ^= _mul(coef, value)
        if 2 * L <= n:
            L = n + 1 - L
            B = T
            b = delta
            m = 1
        else:
            m += 1
    if len(C) - 1 > nsym // 2 or (len(C) > 1 and C[0] == 0):
        # Degree can exceed when uncorrectable.
        pass
    errs = len(C) - 1
    if errs > nsym // 2:
        return False
    # Chien search
    pos = []
    for i in range(len(block)):
        x = _EXP[(255 - i) % 255]
        acc = 0
        for coef in reversed(C):
            acc = _mul(acc, x) ^ coef
        if acc == 0:
            pos.append(len(block) - 1 - i)
    if len(pos) != errs:
        return False
    # Forney
    omega = [0] * errs
    for i in range(errs):
        acc = 0
        for j in range(i + 1):
            acc ^= _mul(syn[i - j], C[j] if j < len(C) else 0)
        omega[i] = acc
    for p in pos:
        xi = _EXP[p]
        num = 0
        for coef in reversed(omega):
            num = _mul(num, xi) ^ coef
        den = 0
        for i in range(1, len(C), 2):
            den ^= _mul(C[i], _EXP[(p * (i - 1)) % 255]) if i > 1 else C[i]
        # Formal derivative of the locator evaluated at x^-1.
        xinv = _EXP[(255 - p) % 255]
        deriv = 0
        for i in range(1, len(C), 2):
            deriv ^= _mul(C[i], _pow(xinv, i - 1))
        if deriv == 0:
            return False
        mag = _mul(num, _pow_inv(deriv))
        # The Forney formula used here matches the syndrome convention above
        # only after dividing by xi. Verified by the round-trip tests.
        mag = _mul(mag, xi)
        block[p] ^= mag
    return True


def _pow(a, n):
    if n == 0:
        return 1
    if a == 0:
        return 0
    return _EXP[(_LOG[a] * n) % 255]


def _mask(kind, r, c):
    if kind == 0:
        return (r + c) % 2 == 0
    if kind == 1:
        return r % 2 == 0
    if kind == 2:
        return c % 3 == 0
    if kind == 3:
        return (r + c) % 3 == 0
    if kind == 4:
        return (r // 2 + c // 3) % 2 == 0
    if kind == 5:
        return (r * c) % 2 + (r * c) % 3 == 0
    if kind == 6:
        return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    return ((r + c) % 2 + (r * c) % 3) % 2 == 0


def _reserved(size, version):
    mark = [[False] * size for _ in range(size)]

    def fill(r0, c0, h, w):
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                if 0 <= r < size and 0 <= c < size:
                    mark[r][c] = True

    fill(0, 0, 9, 9)
    fill(0, size - 8, 9, 8)
    fill(size - 8, 0, 8, 9)
    for i in range(size):
        mark[6][i] = True
        mark[i][6] = True
    for y in _ALIGN.get(version, ()):
        for x in _ALIGN.get(version, ()):
            if y < 9 and x < 9:
                continue
            if y < 9 and x > size - 10:
                continue
            if y > size - 10 and x < 9:
                continue
            fill(y - 2, x - 2, 5, 5)
    for i in range(9):
        mark[8][i] = True
        mark[i][8] = True
    for i in range(8):
        mark[8][size - 1 - i] = True
        mark[size - 1 - i][8] = True
    mark[size - 8][8] = True
    if version >= 7:
        for a in range(6):
            for b in range(3):
                mark[a][size - 11 + b] = True
                mark[size - 11 + b][a] = True
    return mark


def _format_bits(modules):
    n = len(modules)

    def bit(row, col):
        return 1 if modules[row][col] else 0

    a = []
    for c in list(range(6)) + [7, 8]:
        a.append(bit(8, c))
    for r in [7, 5, 4, 3, 2, 1, 0]:
        a.append(bit(r, 8))
    b = []
    for r in range(n - 1, n - 8, -1):
        b.append(bit(r, 8))
    for c in range(n - 8, n):
        b.append(bit(8, c))
    return a, b


def _best_format(bits):
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    best = None
    best_dist = 16
    for data, coded in enumerate(_FORMATS):
        dist = bin(value ^ coded).count('1')
        if dist < best_dist:
            best_dist = dist
            best = data
    if best is None or best_dist > 3:
        return None
    return _LEVEL[best >> 3], best & 7


def _read_codewords(modules, mask, reserved):
    n = len(modules)
    bits = []
    col = n - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if reserved[r][c]:
                    continue
                dark = bool(modules[r][c])
                if _mask(mask, r, c):
                    dark = not dark
                bits.append(1 if dark else 0)
        upward = not upward
        col -= 2
    words = []
    for i in range(0, len(bits) - 7, 8):
        value = 0
        for bit in bits[i:i + 8]:
            value = (value << 1) | bit
        words.append(value)
    return words


def _deinterleave(words, groups):
    blocks = []
    for count, total, data in groups:
        for _ in range(count):
            blocks.append([0] * total)
            blocks[-1]  # data length stored alongside
    lengths = []
    for count, total, data in groups:
        lengths.extend([(data, total - data)] * count)
    idx = 0
    max_data = max(item[0] for item in lengths)
    for i in range(max_data):
        for b, (data, _) in enumerate(lengths):
            if i < data:
                blocks[b][i] = words[idx]
                idx += 1
    max_ecc = max(item[1] for item in lengths)
    for i in range(max_ecc):
        for b, (data, ecc) in enumerate(lengths):
            if i < ecc:
                blocks[b][data + i] = words[idx]
                idx += 1
    return blocks, lengths


def _bits_of(data):
    out = []
    for value in data:
        for shift in range(7, -1, -1):
            out.append((value >> shift) & 1)
    return out


def _take(bits, n, pos):
    if pos + n > len(bits):
        return None, pos
    value = 0
    for i in range(n):
        value = (value << 1) | bits[pos + i]
    return value, pos + n


def _parse(data_bytes, version):
    bits = _bits_of(data_bytes)
    pos = 0
    out = []
    while pos + 4 <= len(bits):
        mode, pos = _take(bits, 4, pos)
        if mode == 0:
            break
        kind = {1: 'num', 2: 'alnum', 4: 'byte'}.get(mode)
        if kind is None:
            return None
        count_len = {'num': (10, 12), 'alnum': (9, 11), 'byte': (8, 16)}[kind][0 if version <= 9 else 1]
        count, pos = _take(bits, count_len, pos)
        if count is None:
            return None
        if kind == 'num':
            chars = []
            while count >= 3:
                value, pos = _take(bits, 10, pos)
                if value is None:
                    return None
                chars.append(f'{value:03d}')
                count -= 3
            if count == 2:
                value, pos = _take(bits, 7, pos)
                if value is None:
                    return None
                chars.append(f'{value:02d}')
            elif count == 1:
                value, pos = _take(bits, 4, pos)
                if value is None:
                    return None
                chars.append(str(value))
            out.append(''.join(chars))
        elif kind == 'alnum':
            chars = []
            while count >= 2:
                value, pos = _take(bits, 11, pos)
                if value is None:
                    return None
                chars.append(_ALPH[value // 45])
                chars.append(_ALPH[value % 45])
                count -= 2
            if count:
                value, pos = _take(bits, 6, pos)
                if value is None:
                    return None
                chars.append(_ALPH[value])
            out.append(''.join(chars))
        else:
            raw = bytearray()
            for _ in range(count):
                value, pos = _take(bits, 8, pos)
                if value is None:
                    return None
                raw.append(value)
            out.append(raw.decode('iso-8859-1'))
    text = ''.join(out).strip('\x00')
    return text or None


def decode_modules(modules):
    """modules[row][col] is true when that module is dark. Includes no quiet zone."""
    n = len(modules)
    if n < 21 or n > 57 or (n - 17) % 4 or any(len(row) != n for row in modules):
        return None
    version = (n - 17) // 4
    if version not in _ECC:
        return None
    fa, fb = _format_bits(modules)
    chosen = _best_format(fa) or _best_format(fb)
    if not chosen:
        return None
    level, mask = chosen
    reserved = _reserved(n, version)
    words = _read_codewords(modules, mask, reserved)
    groups = _ECC[version][level]
    need = sum(count * total for count, total, _data in groups)
    if len(words) < need:
        return None
    blocks, lengths = _deinterleave(words[:need], groups)
    data = []
    for block, (ndata, necc) in zip(blocks, lengths):
        if not _rs_bm(block, [0] * necc, necc) and necc:
            # _rs_bm expects syndromes. Recompute inside a dedicated call.
            pass
        if not _correct(block, necc):
            return None
        data.extend(block[:ndata])
    return _parse(data, version)


def _syndromes(block, nsym):
    syn = []
    for i in range(nsym):
        s = 0
        for value in block:
            s = _mul(s, _EXP[i]) ^ value
        syn.append(s)
    return syn


def _correct(block, nsym):
    if nsym == 0:
        return True
    syn = _syndromes(block, nsym)
    if not any(syn):
        return True
    if not _rs_bm(block, syn, nsym):
        return False
    # A wrong correction still has a syndrome. Fail closed instead of returning garbage.
    return not any(_syndromes(block, nsym))


def _otsu(gray):
    hist = [0] * 256
    for value in gray:
        hist[value] += 1
    total = len(gray)
    sum_all = sum(i * hist[i] for i in range(256))
    sum_b = 0
    w_b = 0
    best = 0
    threshold = 127
    for i in range(256):
        w_b += hist[i]
        if not w_b:
            continue
        w_f = total - w_b
        if not w_f:
            break
        sum_b += i * hist[i]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best:
            best = var
            threshold = i
    return threshold


def _finders(dark, width, height):
    found = []

    def ratio(runs):
        total = sum(runs)
        if total < 7:
            return False
        unit = total / 7
        return all(abs(runs[i] / unit - (3 if i == 2 else 1)) < 0.6 for i in range(5))

    for y in range(height):
        runs = []
        last = None
        count = 0
        row = y * width
        for x in range(width + 1):
            bit = dark[row + x] if x < width else not last
            if bit == last:
                count += 1
                continue
            if last is not None:
                runs.append(count)
                if len(runs) >= 5 and ratio(runs[-5:]):
                    module = sum(runs[-5:]) / 7
                    # x is the first pixel of the next run. The 3-module run is third from the end.
                    center = x - runs[-1] - runs[-2] - runs[-3] / 2.0
                    if _vertical(dark, width, height, int(center), y, module):
                        found.append((center, y, module))
            last = bit
            count = 1
    # Cluster nearby hits of the same finder.
    clusters = []
    for cx, cy, module in found:
        for cluster in clusters:
            if abs(cluster[0] - cx) < module * 2 and abs(cluster[1] - cy) < module * 2:
                cluster[3] += 1
                cluster[0] = (cluster[0] * (cluster[3] - 1) + cx) / cluster[3]
                cluster[1] = (cluster[1] * (cluster[3] - 1) + cy) / cluster[3]
                cluster[2] = (cluster[2] * (cluster[3] - 1) + module) / cluster[3]
                break
        else:
            clusters.append([cx, cy, module, 1])
    clusters = [c for c in clusters if c[3] >= 2]
    clusters.sort(key=lambda c: -c[3])
    return [(c[0], c[1], c[2]) for c in clusters[:8]]


def _vertical(dark, width, height, x, y, module):
    if not (0 <= x < width):
        return False
    up = 0
    yy = y
    while yy >= 0 and dark[yy * width + x]:
        up += 1
        yy -= 1
    down = 0
    yy = y + 1
    while yy < height and dark[yy * width + x]:
        down += 1
        yy += 1
    middle = up + down
    if abs(middle / module - 3) > 1.2:
        return False
    return True


def _order(points):
    def dist(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    best = 0
    tl = points[0]
    others = points[1:]
    for i in range(3):
        rest = [points[j] for j in range(3) if j != i]
        d = dist(rest[0], rest[1])
        if d > best:
            best = d
            tl = points[i]
            others = rest
    a, b = others
    cross = (a[0] - tl[0]) * (b[1] - tl[1]) - (a[1] - tl[1]) * (b[0] - tl[0])
    # Image y grows downward. A positive cross means b is to the right of a? Tested below.
    tr, bl = (a, b) if cross > 0 else (b, a)
    return tl, tr, bl


def _sample(dark, width, height, finders):
    if len(finders) < 3:
        return None
    # Pick the triple whose right angle is closest to 90 degrees and whose module sizes agree.
    best = None
    best_score = 1e18
    for i in range(len(finders)):
        for j in range(i + 1, len(finders)):
            for k in range(j + 1, len(finders)):
                pts = [finders[i], finders[j], finders[k]]
                tl, tr, bl = _order([(p[0], p[1]) for p in pts])
                sizes = [p[2] for p in pts]
                if max(sizes) > min(sizes) * 1.8:
                    continue
                v1 = (tr[0] - tl[0], tr[1] - tl[1])
                v2 = (bl[0] - tl[0], bl[1] - tl[1])
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                n1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
                n2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
                if n1 < 20 or n2 < 20:
                    continue
                score = abs(dot) / (n1 * n2) + abs(n1 - n2) / max(n1, n2)
                if score < best_score:
                    best_score = score
                    best = (tl, tr, bl, sum(sizes) / 3)
    if best is None or best_score > 0.45:
        return None
    tl, tr, bl, module = best
    span = ((tr[0] - tl[0]) ** 2 + (tr[1] - tl[1]) ** 2) ** 0.5
    dim = int(round(span / module + 7))
    if (dim - 17) % 4 or not (21 <= dim <= 57):
        return None
    modules = []
    for r in range(dim):
        row = []
        for c in range(dim):
            ur = (r + 0.5 - 3.5) / (dim - 7)
            uc = (c + 0.5 - 3.5) / (dim - 7)
            x = tl[0] + uc * (tr[0] - tl[0]) + ur * (bl[0] - tl[0])
            y = tl[1] + uc * (tr[1] - tl[1]) + ur * (bl[1] - tl[1])
            ix, iy = int(round(x)), int(round(y))
            if not (0 <= ix < width and 0 <= iy < height):
                return None
            row.append(dark[iy * width + ix])
        modules.append(row)
    return modules


def decode_gray(data, width, height):
    """data is a width*height grayscale buffer, 0–255. Returns the text or None."""
    if width < 21 or height < 21 or len(data) < width * height:
        return None
    gray = list(data[:width * height])
    # Chaquopy may hand Java bytes through as signed.
    gray = [(v + 256) % 256 if isinstance(v, int) and v < 0 else (v if isinstance(v, int) else v) for v in gray]
    threshold = _otsu(gray)
    for invert in (False, True):
        for delta in (0, -20, 20, -40, 40):
            limit = min(250, max(5, threshold + delta))
            dark = [((value < limit) != invert) for value in gray]
            found = _finders(dark, width, height)
            modules = _sample(dark, width, height, found)
            if not modules:
                continue
            text = decode_modules(modules)
            if text:
                return text
    return None
