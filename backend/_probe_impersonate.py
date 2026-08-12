"""primp가 실제로 지원하는 impersonate 값 탐지 (경고는 Rust가 fd2로 직접 찍으므로 OS 레벨로 캡처)."""
import os
import subprocess
import sys

CANDS = [
    "chrome_146", "chrome_142", "chrome_140", "chrome_138", "chrome_136",
    "chrome_134", "chrome_133", "chrome_131", "chrome_130", "chrome_128",
    "firefox_142", "safari_18_5", "edge_134",
]

CHILD = "import primp; primp.Client(impersonate=%r, verify=False)"

ok, bad = [], []
for c in CANDS:
    p = subprocess.run([sys.executable, "-c", CHILD % c],
                       capture_output=True, text=True)
    stderr = (p.stderr or "")
    if "does not exist" in stderr or p.returncode != 0:
        bad.append(c)
    else:
        ok.append(c)

print("VALID  :", ok)
print("INVALID:", bad)
