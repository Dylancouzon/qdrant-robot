"""One owner for face and crop models: priority requests and a replaceable background frame."""
import threading
from collections import deque
from concurrent.futures import Future

from robot.faces import Faces
from robot.things import Crops


class Recognition:
    def __init__(self, preview, faces=None, crops=None):
        self.preview = preview
        self.faces = faces if faces is not None else Faces()
        self.crops = crops if crops is not None else Crops()
        self.condition = threading.Condition()
        self.requests, self.latest = deque(), None
        self.active = None  # the existing source currently being verified, for display ordering
        self.epoch, self.stopped, self.background = 0, False, True
        self.thread = threading.Thread(target=self._run, name="recognition", daemon=True)
        self.thread.start()

    def submit(self, frame):
        with self.condition:
            if not self.stopped and self.background:
                self.latest = (*frame, self.epoch)
                self.condition.notify()

    def call(self, action, mutate=False):
        future = Future()
        with self.condition:
            if self.stopped:
                raise RuntimeError("Recognition is closed")
            if len(self.requests) >= 8:
                raise RuntimeError("Recognition requests are full")
            if mutate:
                self.epoch += 1
                self.latest = None
            self.requests.append((action, future))
            self.condition.notify()
        return future.result()

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.stopped or self.requests or self.latest)
                if self.stopped and not self.requests:
                    return
                request = self.requests.popleft() if self.requests else None
                latest = None if request else self.latest
                if latest:
                    self.latest = None
                    self.active = latest
            if request:
                action, future = request
                try:
                    future.set_result(action(self.faces, self.crops))
                except Exception as error:
                    future.set_exception(error)
            elif latest:
                try:
                    self.preview(*latest)
                except Exception:
                    import traceback
                    traceback.print_exc()
                finally:
                    with self.condition:
                        self.active = None

    def close(self):
        with self.condition:
            self.stopped, self.latest = True, None
            self.condition.notify()
        self.thread.join()

    def pause(self):
        with self.condition:
            self.background, self.latest = False, None
            self.epoch += 1
        self.call(lambda f, c: None)  # drain an in-flight preview; conversation still uses models
