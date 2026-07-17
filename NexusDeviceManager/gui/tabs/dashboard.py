"""
gui/tabs/dashboard.py
─────────────────────
Hardware Diagnostics Dashboard — a read-only property panel that displays the
parsed output of ``ideviceinfo`` in a structured, dark-mode card layout.

Design
------
* A full-width status header pulses between green (connected) and red (offline).
* Property rows are arranged in a QGridLayout inside a styled card frame.
  Each row shows: icon │ field label │ value chip.
* Value chips are colour-coded:
    - Normal:      muted blue-white  (#ccccff)
    - Activated:   green             (#66ff88)
    - Locked/DFU:  red               (#ff6b6b)
    - Unknown:     amber             (#ffaa44)
* A Refresh button triggers a fresh ``DiagnosticsWorker`` scan off-thread.
* Errors from the worker are forwarded via ``scan_error(str)`` so
  ``MainWindow`` can route them to the console tab without tight coupling.

Threading contract
------------------
All ``DiagnosticsWorker`` interactions happen through Qt signals; the dashboard
never calls subprocess functions directly or touches the worker's thread state.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QGridLayout, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.diagnostics import (
    DiagnosticsWorker,
    PROPERTY_KEYS,
    UNKNOWN_SENTINEL,
)

# ── Display metadata ──────────────────────────────────────────────────────────
# Each tuple: (property_key, emoji_icon, human_label)
_DISPLAY_FIELDS: list[tuple[str, str, str]] = [
    ("DeviceName",                           "📱", "Device Name"),
    ("ProductVersion",                       "🔄", "iOS Version"),
    ("ProductType",                          "📦", "Model Identifier"),
    ("SerialNumber",                         "🔢", "Serial Number"),
    ("InternationalMobileEquipmentIdentity", "📡", "IMEI"),
    ("ActivationState",                      "🔑", "Activation State"),
    ("PhoneNumber",                          "📞", "Phone Number"),
    ("ModelNumber",                          "🏷",  "Model Number"),
    ("CPUArchitecture",                      "⚙",  "CPU Architecture"),
    ("HardwarePlatform",                     "🖥",  "Hardware Platform"),
    ("UniqueDeviceID",                       "🆔", "UDID"),
]

# ── Style constants ───────────────────────────────────────────────────────────
_CARD_STYLE = """
    QFrame#prop_card {
        background-color: #1e1e2e;
        border: 1px solid #353550;
        border-radius: 12px;
    }
"""

_VALUE_BASE   = "border-radius:5px; padding:3px 10px; font-family: Consolas, monospace;"
_VALUE_NORMAL = f"color:#c0c0e8; background:#252535; {_VALUE_BASE}"
_VALUE_OK     = f"color:#66ff88; background:#0d1f0d; font-weight:bold; {_VALUE_BASE}"
_VALUE_ERROR  = f"color:#ff6b6b; background:#1f0d0d; font-weight:bold; {_VALUE_BASE}"
_VALUE_WARN   = f"color:#ffaa44; background:#1f180a; {_VALUE_BASE}"


def _value_style_for(key: str, value: str) -> str:
    """Choose the chip colour based on which field this is and its value."""
    if key == "ActivationState":
        if value == "Activated":
            return _VALUE_OK
        if value in ("FactoryLocked", "Unactivated", "WildcardActivated") or \
                value == UNKNOWN_SENTINEL:
            return _VALUE_ERROR
        return _VALUE_WARN      # e.g. "MismatchedIMEI", transitional states
    if value == UNKNOWN_SENTINEL:
        return _VALUE_WARN
    return _VALUE_NORMAL


# ── Dashboard tab ─────────────────────────────────────────────────────────────

class DashboardTab(QWidget):
    """
    Hardware property dashboard panel.

    Public slots (called by MainWindow)
    ------------------------------------
    on_device_connected()   – triggered by TunnelWorker connected signal.
    on_device_disconnected() – triggered by TunnelWorker disconnected signal.
    on_properties_parsed(dict) – slot for DiagnosticsWorker.properties_parsed.

    Outgoing signals
    ----------------
    scan_error(str)  – forwards DiagnosticsWorker errors to the console tab.
    """

    scan_error = pyqtSignal(str)

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value_labels: dict[str, QLabel] = {}
        self._worker:       DiagnosticsWorker | None = None
        self._connected:    bool = False
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # ── Status header ──────────────────────────────────────────────────
        self.status_header = QLabel("⬤   No Device Connected")
        self.status_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.status_header.setMinimumHeight(42)
        self._apply_header_offline()
        root.addWidget(self.status_header)

        # ── Property card ──────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("prop_card")
        card.setStyleSheet(_CARD_STYLE)

        grid = QGridLayout(card)
        grid.setSpacing(8)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setColumnMinimumWidth(0, 32)   # icon
        grid.setColumnMinimumWidth(1, 180)  # label
        grid.setColumnStretch(2, 1)         # value expands

        for row, (key, icon, label_text) in enumerate(_DISPLAY_FIELDS):
            # Icon cell
            icon_lbl = QLabel(icon)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setFont(QFont("Segoe UI Emoji", 14))
            icon_lbl.setFixedWidth(32)
            grid.addWidget(icon_lbl, row, 0)

            # Field-name label
            name_lbl = QLabel(f"{label_text}")
            name_lbl.setStyleSheet(
                "color:#7070a0; font-weight:600; font-size:12px;"
            )
            grid.addWidget(name_lbl, row, 1)

            # Value chip (selectable so users can copy UDID / IMEI etc.)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(_VALUE_NORMAL)
            val_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            val_lbl.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            val_lbl.setMinimumHeight(26)
            grid.addWidget(val_lbl, row, 2)
            self._value_labels[key] = val_lbl

        # Wrap card in a scroll area so it degrades gracefully on small windows
        scroll = QScrollArea()
        scroll.setWidget(card)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        root.addWidget(scroll, stretch=1)

        # ── Bottom action bar ──────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self._status_msg = QLabel("")
        self._status_msg.setStyleSheet("color:#666688; font-style:italic; font-size:11px;")
        bar.addWidget(self._status_msg)
        bar.addStretch()

        self.refresh_btn = QPushButton("🔄   Refresh Hardware Info")
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background:#1a3060;
                border:1px solid #3a5090;
                border-radius:7px;
                padding:4px 18px;
                color:#88aaee;
                font-weight:bold;
                font-size:12px;
            }
            QPushButton:hover    { background:#253880; border-color:#5070c0; color:#aaccff; }
            QPushButton:pressed  { background:#1a2850; }
            QPushButton:disabled { background:#1a1a2a; color:#404060; border-color:#252535; }
        """)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        bar.addWidget(self.refresh_btn)

        root.addLayout(bar)

    # ── Header style helpers ──────────────────────────────────────────────────

    def _apply_header_online(self) -> None:
        self.status_header.setText("⬤   Device Connected — Hardware Info")
        self.status_header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #0d2a0d, stop:1 #1a3a1a);"
            "color:#66ff88; border-radius:10px; padding:10px;"
        )

    def _apply_header_offline(self) -> None:
        self.status_header.setText("⬤   No Device Connected")
        self.status_header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #2a0d0d, stop:1 #3a1a1a);"
            "color:#ff6b6b; border-radius:10px; padding:10px;"
        )

    # ── Public slots (called by MainWindow) ───────────────────────────────────

    def on_device_connected(self) -> None:
        """
        Called by MainWindow when ``TunnelWorker.connection_status_changed``
        fires with ``connected=True``.  Triggers an automatic property scan.
        """
        self._connected = True
        self._apply_header_online()
        self.refresh_btn.setEnabled(True)
        self._run_scan()

    def on_device_disconnected(self) -> None:
        """
        Called by MainWindow when ``TunnelWorker.connection_status_changed``
        fires with ``connected=False``.  Clears all value chips.
        """
        self._connected = False
        self._apply_header_offline()
        self.refresh_btn.setEnabled(False)
        self._status_msg.setText("")
        self._clear_all_values()

    def on_properties_parsed(self, props: dict) -> None:
        """
        Slot for ``DiagnosticsWorker.properties_parsed``.
        Populates every value chip, applying colour-coding per field type.
        """
        self._status_msg.setText("")
        self.refresh_btn.setEnabled(self._connected)

        for key, val_lbl in self._value_labels.items():
            value = props.get(key, "—")
            val_lbl.setText(value if value else "—")
            val_lbl.setStyleSheet(_value_style_for(key, value))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _clear_all_values(self) -> None:
        for lbl in self._value_labels.values():
            lbl.setText("—")
            lbl.setStyleSheet(_VALUE_NORMAL)

    def _on_refresh_clicked(self) -> None:
        self.refresh_btn.setEnabled(False)
        self._run_scan()

    def _run_scan(self) -> None:
        """Spin up a DiagnosticsWorker; guard against concurrent scans."""
        if self._worker and self._worker.isRunning():
            return

        self._status_msg.setText("Scanning device…")

        self._worker = DiagnosticsWorker()
        # Properties result → update value chips
        self._worker.properties_parsed.connect(self.on_properties_parsed)
        # Errors → forwarded up to MainWindow → console tab
        self._worker.error_signal.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

    def _on_worker_error(self, msg: str) -> None:
        """Forward worker errors up to MainWindow (which routes to console)."""
        self.scan_error.emit(msg)
        self._status_msg.setText("⚠  Scan error – see console")

    def _on_scan_finished(self) -> None:
        """Re-enable refresh once the worker has exited."""
        if self._connected:
            self.refresh_btn.setEnabled(True)
        if self._status_msg.text() == "Scanning device…":
            self._status_msg.setText("")
