# ⚡ USB SSH Device Manager

A lightweight PyQt6 desktop application for establishing USB SSH tunnels to connected devices (e.g. jailbroken iPhones) via `iproxy` and running remote diagnostics over SSH — all from a clean dark-themed GUI.

---

## Features

- **USB Tunnel** — Start/stop an `iproxy` tunnel that forwards a local port to the device's SSH port (22) over USB
- **SSH Diagnostics** — Connect via Paramiko and run `uname -a`, `df -h`, and `ps aux` in one click
- **SSH Command Execution** — Execute arbitrary SSH commands and view output in the live log
- **Thread-safe Logging** — All output (tunnel, SSH, errors) streams to a real-time log panel via Qt signals
- **Dark Theme** — Catppuccin Mocha-inspired dark UI

---

## Requirements

- Python 3.10+
- [`libimobiledevice`](https://libimobiledevice.org/) — provides the `iproxy` binary (must be on PATH)
- A connected USB device with SSH enabled (e.g. jailbroken iPhone with OpenSSH)

### Python dependencies

```
PyQt6
paramiko
cryptography
bcrypt
PyNaCl
```

Install via pip:

```bash
pip install PyQt6 paramiko cryptography bcrypt pynacl
```

---

## Project Structure

```
USB_SSH_Manager/
├── main.py              # Entry point
├── core/
│   ├── tunnel.py        # TunnelManager — wraps iproxy subprocess
│   └── executor.py      # CommandExecutor — Paramiko SSH client
├── gui/
│   └── app.py           # MainWindow — PyQt6 UI and styling
└── requirements.txt
```

---

## Usage

```bash
python main.py
```

1. **Connect** your device via USB
2. **Establish Tunnel** — clicks `iproxy` to forward `localhost:<port>` → device port 22
3. Fill in **IP**, **Port**, **Username**, and **Password** in the Connection Settings panel
4. Click **Run Diagnostics** to SSH in and collect system info, or send custom commands
5. **Stop Tunnel** when done — the tunnel is also auto-stopped on window close

### Default credentials

| Field    | Default     |
|----------|-------------|
| IP       | `localhost` |
| Port     | `2222`      |
| Username | `root`      |
| Password | `alpine`    |

> **Note:** The default credentials match the standard OpenSSH setup on jailbroken iOS devices. Change them as needed.

---

## iproxy Setup

`iproxy` is part of [`libimobiledevice`](https://libimobiledevice.org/). Install it for your platform:

| Platform | Command |
|----------|---------|
| macOS    | `brew install libimobiledevice` |
| Windows  | Download from [3u.com](https://www.3u.com/) or use the iTunes driver bundle |
| Linux    | `sudo apt install libimobiledevice-utils` |

Ensure `iproxy` is accessible on your system `PATH`.

---

## Architecture

```
main.py
  └─► MainWindow (gui/app.py)
        ├─► TunnelManager (core/tunnel.py)
        │     └─► subprocess: iproxy <local_port> <remote_port>
        └─► CommandExecutor (core/executor.py)
              └─► paramiko.SSHClient → device over tunnel
```

Log output from both the tunnel subprocess and SSH sessions is routed through a `LogWorker` (Qt signal/slot) to keep UI updates on the main thread.

---

## License

MIT
