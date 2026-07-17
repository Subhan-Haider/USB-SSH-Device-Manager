"""
core/ssh_client.py
──────────────────
Asynchronous SSH command executor — runs entirely in a QThread so the GUI
thread is never blocked by network I/O or connection timeouts.

Key improvements over a bulk-read approach
------------------------------------------
* Output is streamed **line-by-line** via ``iter(stdout.readline, "")`` so
  long-running commands (e.g. ``top -bn1``) produce real-time feedback.
* Both single command strings and lists of commands are accepted; the worker
  iterates and runs each sequentially within a single SSH session.
* Specific exception types are caught and turned into human-readable error
  messages rather than letting raw tracebacks reach the console.
* ``finished_signal`` is *always* emitted (in the ``finally`` block) so
  callers can safely clean up without guarding against missed signals.
"""

import socket
from typing import Union

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal


class SSHWorker(QThread):
    """
    Execute one or more shell commands over an SSH connection.

    Signals
    -------
    log_received(str)
        Emitted for every line of stdout received from the remote shell.
        Callers should connect this to a ``QTextEdit`` append slot.
    output_signal(str)
        Legacy alias of ``log_received`` — kept for backward compatibility.
    error_signal(str)
        Emitted for stderr content and connection-level error messages.
        Consider displaying these in a distinct colour in the console.
    finished_signal()
        Emitted exactly once when the worker exits, whether successfully or
        due to an error.  Use this to re-enable UI buttons and purge the
        worker from the active-worker list.
    """

    log_received    = pyqtSignal(str)
    output_signal   = pyqtSignal(str)   # legacy alias; wired to log_received below
    error_signal    = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(
        self,
        host:     str,
        port:     int,
        username: str,
        password: str,
        command:  Union[str, list],
        parent=None,
    ):
        super().__init__(parent)
        self.host     = host
        self.port     = int(port)
        self.username = username
        self.password = password
        # Normalise: always iterate over a list of commands
        self.commands: list[str] = (
            [command] if isinstance(command, str) else list(command)
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _emit(self, line: str) -> None:
        """Broadcast a log line through both the new and legacy signals."""
        self.log_received.emit(line)
        self.output_signal.emit(line)

    def _stream_command(
        self, client: paramiko.SSHClient, command: str
    ) -> None:
        """
        Execute ``command`` and stream its stdout to ``log_received`` one line
        at a time.  Stderr is flushed to ``error_signal`` after stdout closes.

        Uses ``iter(readline, sentinel)`` which naturally stops when the
        channel is closed by the remote, even for interactive-style commands.
        """
        stdin, stdout, stderr = client.exec_command(command, timeout=30)
        stdin.close()

        # ── Stream stdout line-by-line ─────────────────────────────────────
        try:
            for raw in iter(stdout.readline, ""):
                stripped = raw.rstrip("\n")
                if stripped:
                    self._emit(stripped)
        except socket.timeout:
            self.error_signal.emit(
                f"[SSHWorker] Read timed out while streaming '{command}'."
            )
        except OSError as exc:
            self.error_signal.emit(f"[SSHWorker] Stream I/O error: {exc}")
        except Exception as exc:
            self.error_signal.emit(f"[SSHWorker] Unexpected stream error: {exc}")

        # ── Flush stderr ───────────────────────────────────────────────────
        try:
            err_text = stderr.read().decode("utf-8", errors="replace").strip()
            if err_text:
                for err_line in err_text.splitlines():
                    self.error_signal.emit(err_line)
        except Exception:
            pass  # Non-critical; best-effort stderr capture.

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self) -> None:
        """
        Open one SSH session, run every command sequentially, then close.

        All network and authentication exceptions are caught individually so
        that sudden physical disconnections or bad credentials produce a clean
        error message in the console rather than an unhandled traceback.
        ``finished_signal`` is emitted in the ``finally`` block unconditionally.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname     = self.host,
                port         = self.port,
                username     = self.username,
                password     = self.password,
                timeout      = 5,    # TCP connect timeout
                banner_timeout = 10, # SSH banner exchange timeout
                auth_timeout   = 10, # Authentication phase timeout
            )

            for cmd in self.commands:
                self._emit(f"\n> {cmd}")
                self._stream_command(client, cmd)

        # ── Specific exception handlers ────────────────────────────────────
        except paramiko.AuthenticationException:
            self.error_signal.emit(
                "[SSHWorker] Authentication failed – check username/password."
            )
        except paramiko.BadHostKeyException as exc:
            self.error_signal.emit(f"[SSHWorker] Bad host key: {exc}")
        except paramiko.SSHException as exc:
            self.error_signal.emit(f"[SSHWorker] SSH protocol error: {exc}")
        except socket.timeout:
            self.error_signal.emit(
                f"[SSHWorker] Connection to {self.host}:{self.port} timed out."
            )
        except ConnectionRefusedError:
            self.error_signal.emit(
                f"[SSHWorker] Connection refused at {self.host}:{self.port}. "
                "Is the tunnel running?"
            )
        except ConnectionResetError:
            self.error_signal.emit(
                "[SSHWorker] Connection was reset by the device."
            )
        except EOFError:
            self.error_signal.emit(
                "[SSHWorker] Unexpected end-of-stream – device may have disconnected."
            )
        except OSError as exc:
            self.error_signal.emit(f"[SSHWorker] Network error: {exc}")
        except Exception as exc:
            self.error_signal.emit(f"[SSHWorker] Unexpected error: {exc}")

        finally:
            # Always close the Paramiko client, even on exception paths,
            # then emit finished so callers can clean up.
            try:
                client.close()
            except Exception:
                pass
            self.finished_signal.emit()
