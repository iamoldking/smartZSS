#!/usr/bin/env python3
"""
readzss.py (v2.1) - run the ZSS check on a comma four / comma three from the Mac.

  1. scp zss_check.py (same folder as this file) -> comma@<IP>:/data/
  2. ssh: run it for 10 s; the 0x23 (ZSS) and 0x25 (stock) angles show live here
  3. scp the HTML + CSV + raw CSV back to ./zss_reports/ (the folder you run this command in)
  4. open the HTML report

Usage (on the Mac):
  python3 readzss.py 172.20.10.6               # 10 s
  python3 readzss.py 172.20.10.6 -t 30         # 30 s
  python3 readzss.py 172.20.10.6 --no-open     # don't open the report

Needs: ssh key login to the comma device already working (ssh comma@<IP>).
Read only: nothing on the car or in /data/openpilot is changed.
"""

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK_PY = os.path.join(HERE, "zss_check.py")
REMOTE_PY = "/data/zss_check.py"          # outside /data/openpilot (git clean on update)
LOCAL_DIR = "zss_reports"
SSH_OPTS = ["-o", "ConnectTimeout=5"]


def run(cmd: list) -> None:
  print("$ " + " ".join(cmd), flush=True)
  if subprocess.call(cmd) != 0:
    sys.exit(f"failed: {' '.join(cmd)}")


def main():
  ap = argparse.ArgumentParser(description="ZSS check on a comma device over ssh")
  ap.add_argument("ip", help="comma device IP, e.g. 172.20.10.6 (Settings -> Network)")
  ap.add_argument("-t", "--seconds", type=float, default=10, help="test time in seconds, default 10")
  ap.add_argument("-u", "--user", default="comma", help="ssh user, default comma")
  ap.add_argument("--no-open", action="store_true", help="don't open the HTML report")
  args = ap.parse_args()

  if not os.path.isfile(CHECK_PY):
    sys.exit(f"not found: {CHECK_PY}")
  host = f"{args.user}@{args.ip}"

  # 1. copy the check program to the comma device
  run(["scp", "-q", *SSH_OPTS, CHECK_PY, f"{host}:{REMOTE_PY}"])

  # 2. run it; -tt gives a terminal so the lines show live and Ctrl+C reaches the device
  remote = f"cd /data/openpilot && PYTHONPATH=/data/openpilot python3 -u {REMOTE_PY} -t {args.seconds:g}"
  cmd = ["ssh", "-tt", *SSH_OPTS, host, remote]
  print("$ " + " ".join(cmd), flush=True)
  files = {}
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, errors="replace")
  try:
    for line in p.stdout:
      line = line.rstrip("\r\n")
      print(line, flush=True)
      m = re.match(r"^(report|data|raw):\s+(\S+)$", line.strip())
      if m:
        files[m.group(1)] = m.group(2)
  except KeyboardInterrupt:
    # Ctrl+C also went to the device; keep reading so we get the report lines
    for line in p.stdout:
      line = line.rstrip("\r\n")
      print(line, flush=True)
      m = re.match(r"^(report|data|raw):\s+(\S+)$", line.strip())
      if m:
        files[m.group(1)] = m.group(2)
  p.wait()
  if "report" not in files:
    sys.exit("no report from the comma device (see the messages above)")

  # 3. copy the results back next to where this command was run
  os.makedirs(LOCAL_DIR, exist_ok=True)
  run(["scp", "-q", *SSH_OPTS, *[f"{host}:{f}" for f in files.values()], LOCAL_DIR + "/"])
  local_html = os.path.abspath(os.path.join(LOCAL_DIR, os.path.basename(files["report"])))
  print(f"\nsaved: {os.path.abspath(LOCAL_DIR)}/")
  for f in files.values():
    print(f"  {os.path.basename(f)}")

  # 4. open the report (macOS)
  if not args.no_open and sys.platform == "darwin":
    subprocess.call(["open", local_html])


if __name__ == "__main__":
  main()
