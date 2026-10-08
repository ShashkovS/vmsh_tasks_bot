"""Adapt mathsolvers' pipe/deadline to server signals; vmshpwa/docs/graceful-shutdown.md."""

import multiprocessing

from mathsolvers import MathWorker as BaseMathWorker

from helpers.math_worker_process import run_worker


class MathWorker(BaseMathWorker):
    def __init__(self, method="spawn"):
        super().__init__(method=method)

    def start_worker(self):
        if self.process is not None:
            return
        self.ctx = multiprocessing.get_context(self.method)
        self.pipe_worker, self.pipe_manager = self.ctx.Pipe()
        self.process = self.ctx.Process(
            target=run_worker, args=(self.pipe_worker,), name="vmsh-sympy"
        )
        self.process.start()
        # Spawn imports SymPy afresh. Startup is not a student's calculation
        # budget, especially while test/server processes contend for CPU.
        if not self.pipe_manager.poll(10):
            self._discard_worker()
            raise RuntimeError("SymPy worker startup timed out")
        if self.pipe_manager.recv() != ("ready",):
            self._discard_worker()
            raise RuntimeError("SymPy worker did not become ready")

    def _discard_worker(self):
        process = self.process
        if process.is_alive():
            process.kill()
        process.join(timeout=1)
        if process.is_alive():
            raise RuntimeError("SymPy worker did not stop")
        process.close()
        self.process = None
        self.pipe_worker.close()
        self.pipe_manager.close()
        self.pipe_worker = self.pipe_manager = None

    def run_with_timeout(self, func_name, *args, timeout=1.0, **kwargs):
        self.start_worker()
        task_id = self.task_id = self.task_id + 1
        self.pipe_manager.send((task_id, func_name, args, kwargs))
        if self.pipe_manager.poll(timeout):
            result_id, result = self.pipe_manager.recv()
            if result_id != task_id:
                raise InterruptedError(f"Checker reply mismatch: {task_id=} {result_id=}")
            if isinstance(result, Exception):
                return {"task": args, "error": str(result)}
            return result

        # The child waits for its parent's graceful sentinel on TERM, so a
        # computation deadline must use KILL, followed by join/reap.
        self._discard_worker()
        return {"task": args, "error": f"Таймаут {timeout}с при вычислении выражения"}
