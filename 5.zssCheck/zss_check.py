#!/usr/bin/env python3
"""
zss_check.py (v1.0) - ZSS check on a comma four / comma three (read only).

  Print the 0x23 (ZSS) angle and the 0x25 (stock) angle side by side,
  then write an HTML report (result table + angle plot) and a CSV.

  0x23 uses the ZORRO_STEER factor from toyota_zss.dbc (same as openpilot).
  0x25 = STEER_ANGLE only (1.5 deg steps, no STEER_FRACTION).
  gain = ZSS / stock slope; 1.00 means the DBC factor is right.

Output in /data/personal_settings/zss_reports/:
  zss_<time>.html   result + angle plot
  zss_<time>.csv    one row per 0x25 frame: time, ZSS angle, stock angle, diff

Normally started from the Mac by readzss.py. To run it by hand on the comma device:
  cd /data/openpilot
  PYTHONPATH=/data/openpilot python3 /data/zss_check.py          # 10 s (default)
  PYTHONPATH=/data/openpilot python3 /data/zss_check.py -t 30    # 30 s
  PYTHONPATH=/data/openpilot python3 /data/zss_check.py -t 0     # until Ctrl+C
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
DEFAULT_SECONDS = 10.0
MIN_RANGE_DEG = 20.0                  # steering range needed to measure the gain
PRINT_EVERY_S = 0.5
OUT_DIR = "/data/personal_settings/zss_reports"


def out(*a):
  print(*a, flush=True)               # flush: shows live over ssh


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


def stock_angle(d: bytes) -> float:      # 0x25 STEER_ANGLE 3|12@0- * 1.5 (1.5 deg steps, STEER_FRACTION not used)
  return be_raw(d, 3, 12, True) * 1.5


def gain(rows: list) -> float | None:
  """slope of ZSS vs stock (least squares); needs > MIN_RANGE_DEG of steering range"""
  if len(rows) < 50:
    return None
  xs = [r[2] for r in rows]
  ys = [r[1] for r in rows]
  if max(xs) - min(xs) < MIN_RANGE_DEG:
    return None
  mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
  sxx = sum((x - mx) ** 2 for x in xs)
  return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else None


def offset(rows: list) -> float:
  """ZSS - stock offset (median), because ZSS 0 = wheel position at ZSS power-on"""
  d = sorted(z - s for _, z, s in rows)
  return d[len(d) // 2] if d else 0.0


def svg_plot(rows: list, off: float) -> str:
  """rows: (t, zss, stock). Blue = stock, red = ZSS - offset (lines overlap when ZSS is good)."""
  if len(rows) < 2:
    return "<p>no angle data</p>"
  step = max(1, len(rows) // 1500)
  rows = rows[::step]
  W, H, P = 900, 320, 45
  vals = [v for _, z, s in rows for v in (z - off, s)]
  lo, hi = min(vals), max(vals)
  if hi - lo < 1:
    lo, hi = lo - 1, hi + 1
  t0, t1 = rows[0][0], rows[-1][0]

  def xy(t, v):
    return P + (t - t0) / max(t1 - t0, 1e-6) * (W - 2 * P), H - P - (v - lo) / (hi - lo) * (H - 2 * P)

  o = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="background:#fff;border:1px solid #ccc">']
  if lo < 0 < hi:
    _, y0 = xy(t0, 0)
    o.append(f'<line x1="{P}" y1="{y0:.1f}" x2="{W-P}" y2="{y0:.1f}" stroke="#ddd"/>')
  for v, color in ((lambda r: r[2], "#1f77b4"), (lambda r: r[1] - off, "#d62728")):
    pts = " ".join("%.1f,%.1f" % xy(r[0], v(r)) for r in rows)
    o.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/>')
  o.append(f'<text x="5" y="{P}" font-size="12">{hi:.0f}°</text><text x="5" y="{H-P}" font-size="12">{lo:.0f}°</text>')
  o.append(f'<text x="{P}" y="{H-10}" font-size="12">0 s</text><text x="{W-P-40}" y="{H-10}" font-size="12">{t1-t0:.0f} s</text>')
  o.append(f'<text x="{P+10}" y="20" font-size="13" fill="#1f77b4">■ stock 0x25</text>'
           f'<text x="{P+160}" y="20" font-size="13" fill="#d62728">■ ZSS 0x23 − offset ({off:+.2f}°)</text></svg>')
  return "\n".join(o)


def write_report(rows: list, results: list, off: float) -> tuple[str, str]:
  os.makedirs(OUT_DIR, exist_ok=True)
  stamp = time.strftime("%Y%m%d_%H%M%S")
  csv_path = os.path.join(OUT_DIR, f"zss_{stamp}.csv")
  html_path = os.path.join(OUT_DIR, f"zss_{stamp}.html")
  with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_s", "zss_deg", "stock_deg", "diff_deg"])
    for t, z, s in rows:
      w.writerow([f"{t:.3f}", f"{z:.3f}", f"{s:.1f}", f"{z - s:.3f}"])
  color = {"OK": "#2e7d32", "NOT FOUND": "#c62828", "CHECK": "#c62828"}
  trs = "\n".join(f'<tr><td>{html.escape(a)}</td><td style="color:{color.get(b, "#333")};font-weight:bold">{b}</td>'
                  f'<td>{html.escape(c)}</td></tr>' for a, b, c in results)
  doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>ZSS check {stamp}</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;margin:24px;max-width:1000px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px 8px;text-align:left}}
th{{background:#f3f3f3}}</style></head><body>
<h1>ZSS check</h1>
<p>{time.strftime("%Y-%m-%d %H:%M:%S")} · ZSS factor {ZSS_FACTOR} deg/count (from {html.escape(ZSS_FACTOR_SRC)}) · stock 0x25 = STEER_ANGLE only (1.5° steps)</p>
<table><tr><th>Check</th><th>Result</th><th>Detail</th></tr>{trs}</table>
<h2>Steering angle</h2>{svg_plot(rows, off)}
<p>ZSS 0 = wheel position at ZSS power-on, so the red line is shifted by the offset ({off:+.2f}°).
If the red and blue lines stay on top of each other while turning, ZSS is good.
The blue line moves in 1.5° steps, so a small gap (about ±0.75°) is normal.</p>
<p>Data: {html.escape(os.path.basename(csv_path))} ({len(rows)} rows)</p></body></html>"""
  with open(html_path, "w") as f:
    f.write(doc)
  return html_path, csv_path


def main():
  ap = argparse.ArgumentParser(description="ZSS check v1.0 (read only)")
  ap.add_argument("-t", "--duration", type=float, default=DEFAULT_SECONDS,
                  help=f"seconds to run, default {DEFAULT_SECONDS:.0f} (0 = until Ctrl+C)")
  args = ap.parse_args()

  try:
    import openpilot.cereal.messaging as messaging
    from openpilot.selfdrive.pandad import can_capnp_to_list
  except ImportError as e:
    sys.exit(f"cannot import openpilot ({e}).\nRun:  cd /data/openpilot && PYTHONPATH=/data/openpilot python3 {sys.argv[0]}")

  can_sock = messaging.sub_sock("can", timeout=50)
  zss = stock = None
  n_zss = n_stock = 0
  rows = []                                   # (t, zss, stock), one per 0x25 frame

  out(f"ZSS factor {ZSS_FACTOR} deg/count from {ZSS_FACTOR_SRC}")
  out(">>> Turn the steering wheel left and right now (more than 30 deg each way) <<<")
  if args.duration:
    out(f"    running {args.duration:.0f} s ...  (Ctrl+C to stop early)")
  out(f"{'time':>6} | {'ZSS 0x23':>10} | {'stock 0x25':>10} | {'diff':>7}")
  start = last_print = time.monotonic()
  try:
    while True:
      for _t_ns, frames in can_capnp_to_list(messaging.drain_sock_raw(can_sock, wait_for_one=False)):
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

      now = time.monotonic()
      if now - last_print >= PRINT_EVERY_S:
        z = f"{zss:9.2f}°" if zss is not None else "      ---"
        s = f"{stock:9.1f}°" if stock is not None else "      ---"
        d = f"{zss - stock:+6.2f}°" if zss is not None and stock is not None else "    ---"
        out(f"{now - start:5.1f}s | {z} | {s} | {d}")
        last_print = now
      if args.duration and now - start >= args.duration:
        break
      time.sleep(0.01)
  except KeyboardInterrupt:
    pass

  dur = max(time.monotonic() - start, 1e-3)
  g = gain(rows)
  off = offset(rows)
  rng = (max(r[2] for r in rows) - min(r[2] for r in rows)) if rows else 0.0
  if g is None:
    gain_row = ("ZSS gain vs stock", "INFO",
                f"steering range {rng:.0f} deg, need > {MIN_RANGE_DEG:.0f} deg to measure: turn the wheel more")
  else:
    ok = abs(g - 1.0) <= 0.05
    gain_row = ("ZSS gain vs stock", "OK" if ok else "CHECK",
                f"{g:.3f} (1.00 = DBC factor right; suggested factor {ZSS_FACTOR / g:.9f})")
  results = [
    ("0x23 ZSS found", "OK" if n_zss else "NOT FOUND", f"{n_zss} frames, {n_zss / dur:.1f} Hz"),
    ("0x25 stock angle found", "OK" if n_stock else "NOT FOUND", f"{n_stock} frames, {n_stock / dur:.1f} Hz"),
    gain_row,
    ("ZSS offset", "INFO", f"{off:+.2f} deg (ZSS 0 = wheel position at ZSS power-on)"),
  ]
  out("\n==== result ====")
  for a, b, c in results:
    out(f"{a:24} {b:9} {c}")
  h, c = write_report(rows, results, off)
  out(f"\nreport: {h}\ndata:   {c}")


if __name__ == "__main__":
  main()
