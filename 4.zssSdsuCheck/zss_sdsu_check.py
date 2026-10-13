#!/usr/bin/env python3
"""
zss_sdsu_check.py (v3.3) - simple ZSS / sDSU check on a comma four (read only).

  ZSS : print the 0x23 (ZSS) angle and the 0x25 (stock) angle side by side.
        0x23 uses the ZORRO_STEER factor from toyota_zss.dbc (same as openpilot).
        0x25 = STEER_ANGLE only (1.5 deg steps, no STEER_FRACTION).
        gain = ZSS / stock slope; 1.00 means the DBC factor is right.
  sDSU: 0x2FF found?  and  0x2FF frequency >= 50 Hz  -> PASS

Output in /data/personal_settings/zss_sdsu_reports/:
  zss_sdsu_<time>.html   result + angle plot
  zss_sdsu_<time>.csv    one row per 0x25 frame: time, ZSS angle, stock angle, diff

Run on the comma four:
  cd /data/openpilot
  PYTHONPATH=/data/openpilot python3 /data/zss_sdsu_check.py          # Ctrl+C to stop
  PYTHONPATH=/data/openpilot python3 /data/zss_sdsu_check.py -t 30    # stop after 30 s
"""

import argparse
import csv
import html
import os
import re
import sys
import time

ZSS_DBC = "/data/openpilot/opendbc_repo/opendbc/dbc/toyota_zss.dbc"
ZSS_FACTOR_DEFAULT = 0.004901594652   # used only if the DBC file can't be read
SDSU_MIN_HZ = 50.0         # sDSU PASS threshold
PRINT_EVERY_S = 0.5
OUT_DIR = "/data/personal_settings/zss_sdsu_reports"


def be_raw(d: bytes, start_bit: int, size: int, signed: bool = False) -> int:
  """Motorola (big endian) signal, DBC start bit = MSB."""
  val, pos = 0, start_bit
  for _ in range(size):
    byte, bit = pos // 8, pos % 8
    if byte >= len(d):
      return 0
    val = (val << 1) | ((d[byte] >> bit) & 1)
    pos = pos - 1 if bit else pos + 15
  if signed and val & (1 << (size - 1)):
    val -= 1 << size
  return val


def read_zss_factor(path: str = ZSS_DBC) -> tuple[float, str]:
  """ZORRO_STEER factor from toyota_zss.dbc, e.g. 'SG_ ZORRO_STEER : 7|24@0- (0.004901594652,0)'."""
  try:
    m = re.search(r"SG_\s+ZORRO_STEER\s*:\s*\S+\s*\(([-+0-9.eE]+)\s*,", open(path).read())
    if m:
      return float(m.group(1)), path
  except OSError:
    pass
  return ZSS_FACTOR_DEFAULT, "default (DBC not found)"


ZSS_FACTOR, ZSS_FACTOR_SRC = read_zss_factor()


def zss_angle(d: bytes) -> float:        # 0x23 ZORRO_STEER 7|24@0-, factor from the DBC
  return be_raw(d, 7, 24, True) * ZSS_FACTOR


def gain(rows: list) -> float | None:
  """slope of ZSS vs stock (least squares); needs > 20 deg of steering range"""
  if len(rows) < 50:
    return None
  xs = [r[2] for r in rows]
  ys = [r[1] for r in rows]
  if max(xs) - min(xs) < 20:
    return None
  mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
  sxx = sum((x - mx) ** 2 for x in xs)
  return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else None


def stock_angle(d: bytes) -> float:      # 0x25 STEER_ANGLE 3|12@0- * 1.5 (1.5 deg steps, STEER_FRACTION not used)
  return be_raw(d, 3, 12, True) * 1.5


def svg_plot(rows: list) -> str:
  """rows: (t, zss, stock). Blue = stock, red = ZSS."""
  if len(rows) < 2:
    return "<p>no angle data</p>"
  step = max(1, len(rows) // 1500)
  rows = rows[::step]
  W, H, P = 900, 300, 45
  vals = [v for _, z, s in rows for v in (z, s)]
  lo, hi = min(vals), max(vals)
  if hi - lo < 1:
    lo, hi = lo - 1, hi + 1
  t0, t1 = rows[0][0], rows[-1][0]
  def xy(t, v):
    return P + (t - t0) / max(t1 - t0, 1e-6) * (W - 2 * P), H - P - (v - lo) / (hi - lo) * (H - 2 * P)
  out = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="background:#fff;border:1px solid #ccc">']
  for idx, color in ((2, "#1f77b4"), (1, "#d62728")):
    pts = " ".join("%.1f,%.1f" % xy(r[0], r[idx]) for r in rows)
    out.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/>')
  out.append(f'<text x="5" y="{P}" font-size="12">{hi:.0f}°</text><text x="5" y="{H-P}" font-size="12">{lo:.0f}°</text>')
  out.append(f'<text x="{P}" y="{H-10}" font-size="12">0 s</text><text x="{W-P-40}" y="{H-10}" font-size="12">{t1-t0:.0f} s</text>')
  out.append(f'<text x="{P+10}" y="20" font-size="13" fill="#1f77b4">■ stock 0x25</text>'
             f'<text x="{P+160}" y="20" font-size="13" fill="#d62728">■ ZSS 0x23</text></svg>')
  return "\n".join(out)


def write_report(rows: list, results: list) -> tuple[str, str]:
  os.makedirs(OUT_DIR, exist_ok=True)
  stamp = time.strftime("%Y%m%d_%H%M%S")
  csv_path = os.path.join(OUT_DIR, f"zss_sdsu_{stamp}.csv")
  html_path = os.path.join(OUT_DIR, f"zss_sdsu_{stamp}.html")
  with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_s", "zss_deg", "stock_deg", "diff_deg"])
    for t, z, s in rows:
      w.writerow([f"{t:.3f}", f"{z:.3f}", f"{s:.1f}", f"{z - s:.3f}"])
  color = {"PASS": "#2e7d32", "OK": "#2e7d32", "FAIL": "#c62828", "NOT FOUND": "#c62828"}
  trs = "\n".join(f'<tr><td>{html.escape(a)}</td><td style="color:{color.get(b, "#333")};font-weight:bold">{b}</td>'
                  f'<td>{html.escape(c)}</td></tr>' for a, b, c in results)
  doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>ZSS / sDSU {stamp}</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;margin:24px;max-width:1000px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px 8px;text-align:left}}
th{{background:#f3f3f3}}</style></head><body>
<h1>ZSS / sDSU check</h1>
<p>{time.strftime("%Y-%m-%d %H:%M:%S")} · ZSS factor {ZSS_FACTOR} deg/count (from {html.escape(ZSS_FACTOR_SRC)}) · stock 0x25 = STEER_ANGLE only (1.5° steps) · sDSU PASS at &gt;= {SDSU_MIN_HZ:.0f} Hz</p>
<table><tr><th>Check</th><th>Result</th><th>Detail</th></tr>{trs}</table>
<h2>Steering angle</h2>{svg_plot(rows)}
<p>ZSS 0 = wheel position at ZSS power-on, so the two lines have a constant offset.
If the gap stays the same while turning, ZSS is good.</p>
<p>Data: {html.escape(os.path.basename(csv_path))} ({len(rows)} rows)</p></body></html>"""
  with open(html_path, "w") as f:
    f.write(doc)
  return html_path, csv_path


def main():
  ap = argparse.ArgumentParser(description="ZSS / sDSU check v3.3 (read only)")
  ap.add_argument("-t", "--duration", type=float, default=0, help="seconds to run (0 = until Ctrl+C)")
  args = ap.parse_args()

  try:
    import openpilot.cereal.messaging as messaging
    from openpilot.selfdrive.pandad import can_capnp_to_list
  except ImportError as e:
    sys.exit(f"cannot import openpilot ({e}).\nRun:  cd /data/openpilot && PYTHONPATH=/data/openpilot python3 {sys.argv[0]}")

  can_sock = messaging.sub_sock("can", timeout=50)
  zss = stock = None
  n_zss = n_stock = n_sdsu = 0
  sdsu_first = sdsu_last = None
  rows = []                                   # (t, zss, stock), one per 0x25 frame
  start = last_print = time.monotonic()

  print(f"ZSS factor {ZSS_FACTOR} deg/count from {ZSS_FACTOR_SRC}")
  print(f"{'time':>6} | {'ZSS 0x23':>10} | {'stock 0x25':>10} | {'diff':>7}")
  try:
    while True:
      for t_ns, frames in can_capnp_to_list(messaging.drain_sock_raw(can_sock, wait_for_one=False)):
        for addr, dat, src in frames:
          if src != 0:
            continue
          if addr == 0x23:
            zss = zss_angle(bytes(dat))
            n_zss += 1
          elif addr == 0x25:
            stock = stock_angle(bytes(dat))
            n_stock += 1
            if zss is not None:
              rows.append((time.monotonic() - start, zss, stock))
          elif addr == 0x2FF:
            t = t_ns * 1e-9
            sdsu_first = sdsu_first or t
            sdsu_last = t
            n_sdsu += 1

      now = time.monotonic()
      if now - last_print >= PRINT_EVERY_S:
        z = f"{zss:9.2f}°" if zss is not None else "      ---"
        s = f"{stock:9.1f}°" if stock is not None else "      ---"
        d = f"{zss - stock:+6.2f}°" if zss is not None and stock is not None else "    ---"
        print(f"{now - start:5.1f}s | {z} | {s} | {d}")
        last_print = now
      if args.duration and now - start >= args.duration:
        break
      time.sleep(0.01)
  except KeyboardInterrupt:
    pass

  dur = max(time.monotonic() - start, 1e-3)
  g = gain(rows)
  hz = (n_sdsu - 1) / (sdsu_last - sdsu_first) if n_sdsu > 1 and sdsu_last > sdsu_first else 0.0
  results = [
    ("0x23 ZSS found", "OK" if n_zss else "NOT FOUND", f"{n_zss} frames, {n_zss / dur:.1f} Hz"),
    ("0x25 stock angle found", "OK" if n_stock else "NOT FOUND", f"{n_stock} frames, {n_stock / dur:.1f} Hz"),
    ("ZSS gain vs stock", "INFO",
     f"{g:.3f} (1.00 = DBC factor right; suggested factor {ZSS_FACTOR / g:.6f})" if g else "turn the wheel > 20 deg to measure"),
    ("0x2FF sDSU found", "OK" if n_sdsu else "NOT FOUND", f"{n_sdsu} frames"),
    ("0x2FF sDSU >= 50 Hz", "PASS" if n_sdsu and hz >= SDSU_MIN_HZ else "FAIL", f"{hz:.1f} Hz (need >= {SDSU_MIN_HZ:.0f} Hz)"),
  ]
  print("\n==== result ====")
  for a, b, c in results:
    print(f"{a:24} {b:9} {c}")
  h, c = write_report(rows, results)
  print(f"\nreport: {h}\ndata:   {c}")


if __name__ == "__main__":
  main()
