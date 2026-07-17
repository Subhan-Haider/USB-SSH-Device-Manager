import urllib.request
import subprocess
import os

WHEELS = [
    {
        "fname": "paramiko-5.0.0-py3-none-any.whl",
        "url": "https://files.pythonhosted.org/packages/82/5b/eadf6d45de38d30ab603f49393b6cd2cbe7e233af8cf90197e32782b68a9/paramiko-5.0.0-py3-none-any.whl"
    },
    {
        "fname": "bcrypt-5.0.0-cp39-abi3-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/9f/b9/9d9a641194a730bda138b3dfe53f584d61c58cd5230e37566e83ec2ffa0d/bcrypt-5.0.0-cp39-abi3-win_amd64.whl"
    },
    {
        "fname": "cryptography-49.0.0-cp311-abi3-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/1f/09/f42b1d190c5ba75f72062a387f8030d1d75f6ab035788f1d9c4b01de6525/cryptography-49.0.0-cp311-abi3-win_amd64.whl"
    },
    {
        "fname": "cffi-2.1.0-cp311-cp311-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/f9/c8/6c2de1d55cf35ef8b92885d5ef280790f0fb9634d87ea1cc315176aecd61/cffi-2.1.0-cp311-cp311-win_amd64.whl"
    },
    {
        "fname": "pycparser-2.22-py3-none-any.whl",
        "url": "https://files.pythonhosted.org/packages/13/a3/a812df4e2dd5696d1f351d58b8fe16a405b234ad2886a0dab9183fb78109/pycparser-2.22-py3-none-any.whl"
    },
    {
        "fname": "invoke-3.0.3-py3-none-any.whl",
        "url": "https://files.pythonhosted.org/packages/5a/de/bbc12563bbf979618d17625a4e753ff7a078523e28d870d3626daa97261a/invoke-3.0.3-py3-none-any.whl"
    },
    {
        "fname": "pynacl-1.6.2-cp38-abi3-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/41/ad/334600e8cacc7d86587fe5f565480fde569dfb487389c8e1be56ac21d8ac/pynacl-1.6.2-cp38-abi3-win_amd64.whl"
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
            print(f"  {len(data):,} / {total:,} bytes", end='\r')
    print()
    with open(fname, 'wb') as f:
        f.write(data)
    print(f"  Saved {fname} ({len(data):,} bytes) OK")
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
    print(f"\nInstalling {len(downloaded)} packages with --no-deps...")
    subprocess.run(["py", "-3.11", "-m", "pip", "install"] + downloaded + ["--no-deps", "--force-reinstall"])
    print("\nDone! Now running the app...")
    subprocess.run(["py", "-3.11", "main.py"])
