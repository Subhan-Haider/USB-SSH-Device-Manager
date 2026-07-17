import urllib.request
import json
import subprocess
import os

packages = ["paramiko", "bcrypt", "cryptography", "invoke", "PyNaCl", "cffi", "pycparser"]

def get_wheel(pkg):
    url = f"https://pypi.org/pypi/{pkg}/json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    
    for release in data["urls"]:
        fname = release["filename"]
        if fname.endswith(".whl"):
            if "win_amd64" in fname or "any.whl" in fname:
                # Basic filter for Python 3.11 compatibility for this test
                if "cp311" in fname or "abi3" in fname or "py3-none-any" in fname or "cp314" in fname or "cp39" in fname or "cp38" in fname:
                    return fname, release["url"]
    return None, None

downloaded = []
for pkg in packages:
    try:
        fname, url = get_wheel(pkg)
        if not fname:
            continue
        if not os.path.exists(fname):
            print(f"Downloading {fname} from {url}...")
            urllib.request.urlretrieve(url, fname)
            print(f"Saved {fname}")
        downloaded.append(fname)
    except Exception as e:
        print(f"Failed on {pkg}: {e}")
        
if downloaded:
    print(f"Installing all downloaded wheels...")
    subprocess.run(["py", "-3.11", "-m", "pip", "install"] + downloaded + ["--no-index", "--find-links=."], check=False)
