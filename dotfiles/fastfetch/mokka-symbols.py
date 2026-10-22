# Genera el logo de símbolos a partir de la geometría de mokka-fastfetch.png (1544 px)
import sys
W, H = 20, 10            # celdas; cada celda = 2 «píxeles» verticales (▀ ▄)
S = 1544
def inside_poly(x, y, pts):
    c = False
    for i in range(len(pts)):
        x1, y1 = pts[i]; x2, y2 = pts[i-1]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: c = not c
    return c
def cat(x, y):
    if ((x-770)/530)**2 + ((y-830)/465)**2 <= 1: return True
    if inside_poly(x, y, [(300,290),(320,600),(600,400)]): return True
    if inside_poly(x, y, [(1110,255),(1175,540),(890,390)]): return True
    if inside_poly(x, y, [(455,1150),(1080,1150),(1112,1544),(398,1544)]): return True
    return False
def px(x, y):  # 0 = nada, -1 = gato, 1..6 = franja
    if (x-770)**2 + (y-772)**2 > 770**2: return 0
    if cat(x, y): return -1
    k = int((x + y) / 1544 * 6.2 - 0.6)   # franjas diagonales ↗
    return max(1, min(6, k + 1 - 0)) if k >= 0 else 1
rows = []
for r in range(H):
    line = []
    for c in range(W):
        x = (c + .5) * S / W
        t = px(x, (r + .25) * S / H); b = px(x, (r + .75) * S / H)
        if t > 0 and b > 0: line.append((t, '█'))
        elif t > 0: line.append((t, '▀'))
        elif b > 0: line.append((b, '▄'))
        else: line.append((0, ' '))
    rows.append(line)
def put(r, c, text, col):
    for i, ch in enumerate(text): rows[r][c+i] = (col, ch)
# rasgos (7 = lavanda, 8 = lazo)
col = lambda x: int(x / S * W); row = lambda y: int(y / S * H)
put(row(660), col(600), '◠', 7)
put(row(660), col(1000), '◠', 7)
put(row(860), col(830), 'ω', 7)
put(row(1290), col(790), '▶◀', 8)
out = []
for line in rows:
    s, cur = '', None
    for colr, ch in line:
        if ch != ' ' and colr != cur: s += f'${colr}'; cur = colr
        s += ch
    out.append(s.rstrip())
print('\n'.join(out))
