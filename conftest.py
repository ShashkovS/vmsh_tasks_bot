"""Shared import-time test setup before either adapter's conftest is loaded."""

import atexit
import os
import shutil
import tempfile

# prometheus_client chooses its ValueClass at first import. Legacy handlers
# can import it before pwa_tests/conftest.py when both suites run together.
# See pwa_tests/reports/check-optimization-20261003/README.md.
_metrics_directory = tempfile.mkdtemp(prefix="vmsh-prometheus-tests-")
os.environ["PROMETHEUS_MULTIPROC_DIR"] = _metrics_directory
atexit.register(shutil.rmtree, _metrics_directory, ignore_errors=True)
