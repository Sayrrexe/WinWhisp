from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def _ensure_qapplication():
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        existing.quit()
        existing.deleteLater()
    if QCoreApplication.instance() is None:
        QApplication(sys.argv[:1])
    yield
