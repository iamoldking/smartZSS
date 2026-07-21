#!/usr/bin/env python3
"""
Read CAN ID 0x23 (SECONDARY_STEER_ANGLE) on a comma three,
decode it with toyota_zss.dbc, and print the ZORRO_STEER value to the terminal.

Prerequisites:
  1. Place toyota_zss.dbc at:
       /data/openpilot/opendbc_repo/opendbc/dbc/toyota_zss.dbc
  2. openpilot itself must be running (boardd active), so the 'can' topic
     actually has data being published.

Usage on comma three (after SSH in):
  export PYTHONPATH=/data/openpilot
  python3 readzss.py

  # If the ZSS is wired to a different bus than 0:
  python3 readzss.py --bus 1
"""

import argparse
import cereal.messaging as messaging
from opendbc.can.parser import CANParser

MSG_NAME = "SECONDARY_STEER_ANGLE"   # corresponds to CAN ID 0x23 (35)
SIGNAL_NAME = "ZORRO_STEER"
DBC_NAME = "toyota_zss"              # corresponds to opendbc/dbc/toyota_zss.dbc (no extension)


def main():
  parser = argparse.ArgumentParser(description="Read the ZORRO_STEER value from CAN 0x23")
  parser.add_argument("--bus", type=int, default=0, help="CAN bus number the ZSS is wired to, default 0")
  args = parser.parse_args()

  # messages: [(message_name, expected_frequency_hz)]
  # frequency=0 means no periodicity check, so it won't be marked as timed out
  messages = [(MSG_NAME, 0)]
  cp = CANParser(DBC_NAME, messages, args.bus)

  can_sock = messaging.sub_sock('can')
  print(f"Listening on bus={args.bus} for {MSG_NAME} (0x23), decoding {SIGNAL_NAME} ...  (Ctrl+C to stop)")

  try:
    while True:
      msgs = messaging.drain_sock(can_sock, wait_for_one=True)
      if not msgs:
        continue

      # cp.update() expects [(t_nanos, [(address, dat, src), ...]), ...]
      strings = [(evt.logMonoTime, [(c.address, c.dat, c.src) for c in evt.can]) for evt in msgs]

      updated_addrs = cp.update(strings)

      if 35 in updated_addrs:  # 0x23 = 35
        zorro_steer = cp.vl[MSG_NAME][SIGNAL_NAME]
        print(f"ZORRO_STEER = {zorro_steer:.3f} deg")
  except KeyboardInterrupt:
    print("\nStopped listening.")


if __name__ == "__main__":
  main()
