#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Lanza frida dentro de un PTY completo via pty.spawn() para que vea un TTY real."""

import argparse
import os
import pty
import sys

parser = argparse.ArgumentParser()
parser.add_argument("script")
parser.add_argument("--host", default="127.0.0.1:27042")
parser.add_argument("--process", default="Gadget")
args = parser.parse_args()

frida_bin = os.path.expanduser("~/.local/bin/frida")
cmd = [frida_bin, "-H", args.host, args.process, "-l", args.script]


def read_cb(fd):
    data = os.read(fd, 4096)
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
    return data


print(f"LAUNCHING: {' '.join(cmd)}", flush=True)
pty.spawn(cmd, read_cb)
