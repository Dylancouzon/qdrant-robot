#!/usr/bin/env python3
"""Talk to the robot from the Mac: streams the Mac microphone to `robot.main --listen` and plays
its answers. Every model still runs on the Jetson. Half duplex: the microphone is muted while
an answer plays, so the robot does not hear itself (use headphones to talk over it).

    .venv/bin/python tools/talk.py [--host qdrant-robot.local] [--port 7070]
"""
import argparse
import socket
import struct
import threading
import time

import numpy as np
import sounddevice as sd

RATE_IN, RATE_OUT, CHUNK = 16000, 24000, 1280  # 80 ms chunks, as the robot expects
TAIL_S = 0.3                                    # stay muted this long after an answer ends


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="qdrant-robot.local")
    p.add_argument("--port", type=int, default=7070)
    a = p.parse_args()
    conn = socket.create_connection((a.host, a.port))
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    muted_until = [0.0]  # the microphone stays muted until the queued answer audio has played
    out = sd.OutputStream(samplerate=RATE_OUT, channels=1, dtype="int16")
    out.start()

    def answers() -> None:
        played_until = 0.0  # when the audio queued so far finishes playing
        with conn.makefile("rb") as f:  # buffered: read(n) returns n bytes, or fewer at the end
            while len(header := f.read(4)) == 4:
                size = struct.unpack("<I", header)[0]
                if len(data := f.read(size)) < size:
                    break
                pcm = np.frombuffer(data, np.int16)
                played_until = max(played_until, time.time()) + len(pcm) / RATE_OUT
                muted_until[0] = max(muted_until[0], played_until + TAIL_S)
                out.write(pcm)

    threading.Thread(target=answers, daemon=True).start()
    print("talking to the robot; Ctrl-C to stop")
    with sd.InputStream(samplerate=RATE_IN, channels=1, dtype="int16", blocksize=CHUNK) as mic:
        while True:
            data, _ = mic.read(CHUNK)
            if time.time() < muted_until[0]:
                data = np.zeros_like(data)  # silence keeps the robot's clock and VAD running
            conn.sendall(data.tobytes())


if __name__ == "__main__":
    main()
