"""
core/diagnostics.py
───────────────────
Background worker that queries ``ideviceinfo`` and emits a parsed hardware
property dictionary via a Qt signal, keeping the GUI thread completely free.

Architecture
------------
* ``DiagnosticsWorker(QThread)`` runs the subprocess off the main thread.
* ``_parse_kv`` handles the plain key: value format produced by ``ideviceinfo``.
* Every property that is absent or unparseable defaults to ``UNKNOWN_SENTINEL``
  so the dashboard always has a value to display (never crashes on missing keys).
* ``ideviceinfo`` returning a non-zero exit code (DFU / recovery mode / no
  device) is treated as a soft failure: sentinel values are emitted and an
  informational message is forwarded to ``error_signal``.
"""

import os
import sys
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

# ── PATH bootstrap ────────────────────────────────────────────────────────────
# Locate bundled libimobiledevice binaries so this module works independently
# of whether main_window.py has already set PATH.
_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_CANDIDATE_TOOL_DIRS = [
    os.path.join(_PROJECT_ROOT, "tools"),
    os.path.join(os.path.dirname(_PROJECT_ROOT), "USB_SSH_Manager", "tools"),
]
for _td in _CANDIDATE_TOOL_DIRS:
    if os.path.isdir(_td) and _td not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _td + os.pathsep + os.environ.get("PATH", "")
        break

# ── Constants ──────────────────────────────────────────────────────────────────

#: Displayed whenever a property cannot be read (DFU, locked USB bus, etc.)
UNKNOWN_SENTINEL = "Unknown / DFU Mode"

#: Ordered list of property keys the dashboard wants to display.
#: Add or remove keys here to adjust what gets parsed/forwarded.
PROPERTY_KEYS: list[str] = [
    "DeviceName",
    "ProductVersion",
    "ProductType",
    "SerialNumber",
    "InternationalMobileEquipmentIdentity",
    "ActivationState",
    "PhoneNumber",
    "ModelNumber",
    "CPUArchitecture",
    "HardwarePlatform",
    "UniqueDeviceID",
]


# ── Parser helpers ─────────────────────────────────────────────────────────────

def _parse_kv(raw: str) -> dict:
    """
    Parse the ``key: value`` text output of ``ideviceinfo`` into a dict.

    ``ideviceinfo`` (without ``-x``) produces lines like::

        DeviceName: My iPhone
        ProductVersion: 17.2
        ActivationState: Activated

    Any key not present in ``PROPERTY_KEYS`` is ignored.  Keys present in
    ``PROPERTY_KEYS`` but absent from the output receive ``UNKNOWN_SENTINEL``.

    Parameters
    ----------
    raw:
        Raw stdout string from ``ideviceinfo``.

    Returns
    -------
    dict
        Mapping of every ``PROPERTY_KEYS`` entry to its parsed value or sentinel.
    """
    result: dict[str, str] = {k: UNKNOWN_SENTINEL for k in PROPERTY_KEYS}

    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key   = key.strip()
        value = value.strip()
        if key in result and value:
            result[key] = value

    return result


# ── Worker thread ──────────────────────────────────────────────────────────────

class DiagnosticsWorker(QThread):
    """
    Off-thread hardware property scanner.

    Call ``start()`` after connecting signals; the thread runs once and exits.

    Signals
    -------
    properties_parsed(dict)
        Emitted with the full ``{key: value}`` property map.  Keys are always
        the entries of ``PROPERTY_KEYS``; values default to ``UNKNOWN_SENTINEL``
        when absent or when the device is unreachable (DFU / locked USB bus).
    error_signal(str)
        Human-readable diagnostic message forwarded to the UI console.
        Emitting this signal does *not* prevent ``properties_parsed`` from
        firing – both always fire in sequence.
    """

    properties_parsed = pyqtSignal(dict)   # spec-required signal name
    error_signal      = pyqtSignal(str)

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _popen_kwargs() -> dict:
        """Return platform-specific kwargs that suppress the CMD window."""
        kw: dict = {}
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        return kw

    def _run_ideviceinfo(self) -> str:
        """
        Execute ``ideviceinfo`` and return its stdout, or ``""`` on any failure.

        Failure paths (FileNotFoundError, timeout, non-zero exit) all emit a
        message to ``error_signal`` so the console tab can inform the user,
        then return an empty string so ``_parse_kv`` will fill sentinel values.
        """
        try:
            proc = subprocess.run(
                ["ideviceinfo"],
                capture_output=True,
                text=True,
                timeout=5,
                **self._popen_kwargs(),
            )

            if proc.returncode != 0:
                # Non-zero usually means DFU mode, locked USB bus, or no device
                stderr_msg = proc.stderr.strip() or "non-zero exit code"
                self.error_signal.emit(
                    f"[Diagnostics] ideviceinfo failed: {stderr_msg} – "
                    "device may be in DFU/recovery mode or USB is locked."
                )
                return ""

            return proc.stdout

        except FileNotFoundError:
            self.error_signal.emit(
                "[Diagnostics] 'ideviceinfo' not found. "
                "Ensure libimobiledevice is installed and in tools/ or PATH."
            )
        except subprocess.TimeoutExpired:
            self.error_signal.emit(
                "[Diagnostics] ideviceinfo timed out – device may be busy."
            )
        except Exception as exc:
            self.error_signal.emit(
                f"[Diagnostics] Unexpected error running ideviceinfo: {exc}"
            )

        return ""

    # ── QThread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Fetch hardware properties and emit them via ``properties_parsed``.

        Always emits ``properties_parsed`` – even on failure the dict contains
        sentinel values, so the dashboard always has something meaningful to show.
        """
        raw   = self._run_ideviceinfo()
        props = _parse_kv(raw)
        self.properties_parsed.emit(props)
