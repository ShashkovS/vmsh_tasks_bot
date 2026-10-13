"""Signal boundary for the owned SymPy child; vmshpwa/docs/graceful-shutdown.md."""

import signal


def run_worker(pipe):
    # systemd KillMode=control-group sends TERM to both parent and child. The
    # parent's pipe sentinel closes this worker after accepted checks drain.
    # Calculation deadlines use kill(), independently of server shutdown.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    from mathsolvers.math_worker.worker_module import worker_loop

    pipe.send(("ready",))
    worker_loop(pipe)
