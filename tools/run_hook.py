#!/usr/bin/env python3
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


