#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate

python3 - <<'PY'
import subprocess, sys, json, time
from pathlib import Path

SOLUTIONS = {
    "approximately_equal": (
        "import math\n"
        "def approximately_equal(a, b, rel=1e-9, abs_tol=1e-12):\n"
        "    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)\n",
        "assert approximately_equal(0.1+0.2,0.3)\n"
        "assert approximately_equal(0.0,1e-12)\n"
        "assert approximately_equal(1.0,1.0)\n"
        "assert not approximately_equal(1.0,2.0)\n"
        "assert not approximately_equal(1e-9,1e9)\n"
        "print('PASS')"
    ),
    "merge_intervals": (
        "def merge_intervals(intervals):\n"
        "    if not intervals: return []\n"
        "    s = sorted(intervals)\n"
        "    out = [list(s[0])]\n"
        "    for lo, hi in s[1:]:\n"
        "        if lo <= out[-1][1]:\n"
        "            out[-1][1] = max(out[-1][1], hi)\n"
        "        else:\n"
        "            out.append([lo, hi])\n"
        "    return out\n",
        "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]\n"
        "assert merge_intervals([])==[]\n"
        "assert merge_intervals([[1,4],[4,5]])==[[1,5]]\n"
        "print('PASS')"
    ),
    "binary_search_leftmost": (
        "def binary_search_leftmost(arr, x):\n"
        "    lo, hi, res = 0, len(arr)-1, -1\n"
        "    while lo <= hi:\n"
        "        mid = (lo+hi)//2\n"
        "        if arr[mid] == x:\n"
        "            res = mid; hi = mid-1\n"
        "        elif arr[mid] < x:\n"
        "            lo = mid+1\n"
        "        else:\n"
        "            hi = mid-1\n"
        "    return res\n",
        "assert binary_search_leftmost([1,2,2,2,3],2)==1\n"
        "assert binary_search_leftmost([1,2,3],4)==-1\n"
        "assert binary_search_leftmost([],1)==-1\n"
        "assert binary_search_leftmost([2,2,2],2)==0\n"
        "print('PASS')"
    ),
    "valid_ipv4": (
        "def valid_ipv4(s):\n"
        "    parts = s.split('.')\n"
        "    if len(parts) != 4: return False\n"
        "    for p in parts:\n"
        "        if not p.isdigit(): return False\n"
        "        if p != '0' and p[0] == '0': return False\n"
        "        if not 0 <= int(p) <= 255: return False\n"
        "    return True\n",
        "assert valid_ipv4('192.168.1.1')\n"
        "assert not valid_ipv4('256.1.1.1')\n"
        "assert not valid_ipv4('01.2.3.4')\n"
        "assert not valid_ipv4('1.2.3')\n"
        "assert valid_ipv4('0.0.0.0')\n"
        "print('PASS')"
    ),
}

K = 20
print("task                     passes/K   avg_sec")
print("-" * 45)
summary = {}
for name, (code, test) in SOLUTIONS.items():
    passes = 0
    durations = []
    for i in range(K):
        p = Path("/tmp/id_" + name + "_" + str(i) + ".py")
        p.write_text(code + "\n\n" + test)
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and "PASS" in r.stdout:
                passes += 1
            durations.append(time.time() - t0)
        except subprocess.TimeoutExpired:
            durations.append(15.0)
    avg = sum(durations) / len(durations) if durations else 0.0
    summary[name] = {"passes": passes, "K": K, "avg_sec": round(avg, 3)}
    print(name.ljust(24), str(passes).rjust(3) + "/" + str(K), "  ", round(avg, 3))

Path("signals_adv/identity_control.json").write_text(json.dumps(summary, indent=2))
print()
print("=== Verdict ===")
all_clean = all(s["passes"] == K for s in summary.values())
if all_clean:
    print("  IDENTITY CONTROL CLEAN - measurement floor is 20/20 per task")
    print("  Any failure observed later is attributable to model output.")
else:
    print("  IDENTITY CONTROL BROKEN - known-good code fails its own test.")
    print("  Every prior failure count is contaminated. Fix this before continuing.")
    for name, s in summary.items():
        if s["passes"] < K:
            print("  ", name, str(s["passes"]) + "/" + str(K))
PY
