import urllib.request
import subprocess
import os

WHEELS = [
    {
        "fname": "pyqt6-6.11.0-cp310-abi3-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/6f/85/dd9f03d78d87460e109e0121cd6201c5802bdd655656bf2780e964870fea/pyqt6-6.11.0-cp310-abi3-win_amd64.whl"
    },
    {
        "fname": "pyqt6_qt6-6.11.1-py3-none-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/fa/f1/70e83c23bf897c7f5025aa100482f482038ef70232dc27b407659d941fbf/pyqt6_qt6-6.11.1-py3-none-win_amd64.whl"
    },
    {
        "fname": "pyqt6_sip-13.11.1-cp311-cp311-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/4a/d6/c40e8ae38a6e2bce9e837b64688f55746bfdad1aa557eb733fb5e90edd7c/pyqt6_sip-13.11.1-cp311-cp311-win_amd64.whl"
    },
]

def download(url, fname):
    print(f"Downloading {fname}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get('Content-Length', 0))
        data = b""
        while True:
            chunk = r.read(131072)
            if not chunk:
                break
            data += chunk
            if total:
                pct = len(data) * 100 // total
                print(f"  {len(data):,}/{total:,} bytes ({pct}%)", end='\r')
    print()
    with open(fname, 'wb') as f:
        f.write(data)
    print(f"  Saved {fname} ({len(data):,} bytes)")
    return True

downloaded = []
for entry in WHEELS:
    fname = entry["fname"]
    if os.path.exists(fname) and os.path.getsize(fname) > 10000:
        print(f"Already have {fname}")
        downloaded.append(fname)
        continue
    try:
        if download(entry["url"], fname):
            downloaded.append(fname)
    except Exception as e:
        print(f"  FAILED {fname}: {e}")

if downloaded:
    print(f"\nInstalling {len(downloaded)} PyQt6 packages...")
    subprocess.run(["py", "-3.11", "-m", "pip", "install"] + downloaded + ["--no-deps", "--force-reinstall"])
    print("\nPyQt6 installed! Testing...")
    subprocess.run(["py", "-3.11", "-c", "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"])
