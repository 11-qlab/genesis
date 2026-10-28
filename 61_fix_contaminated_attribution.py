#!/usr/bin/env python3
"""Fix: contaminated_run means infra>valid. That IS an infra failure.
The prior scoring let template_wrong win unconditionally."""
from pathlib import Path
p = Path(__file__).resolve().parent / "60_attribute_failures.py"
src = p.read_text()

old = '''    if h == "template_wrong":
        if kind == "contaminated_run" and a.get("infra",0) > a.get("valid",0): return 1.0
        if kind == "zero_valid" and a.get("valid",1) == 0: return 1.0
        return 0.0'''
new = '''    if h == "infra":
        # contaminated_run means infra>valid -> infra failure by definition
        if kind == "contaminated_run": return 1.0
        if any(k in reason for k in ("rate limit","timeout","connection",
                                     "network","429","503","backend","abort")): return 1.0
        return 0.0
    if h == "template_wrong":
        if kind == "zero_valid" and a.get("valid",1) == 0: return 1.0
        return 0.0'''
assert old in src, "pattern not found — 60_ was edited, patch aborted"
# also remove the earlier duplicate infra block (lines ~30-32)
src = src.replace(
    '''    if h == "infra":
        return 1.0 if any(k in reason for k in
            ("rate limit","timeout","connection","network","429","503","backend","abort")) else 0.0
''', '')
p.write_text(src.replace(old, new))
print("patched 60_attribute_failures.py: contaminated_run -> infra")
