#!/usr/bin/env python3
from pathlib import Path
p = Path(__file__).resolve().parent / "70_async_router.py"
src = p.read_text()
old = '''        for n, b in buckets.items(): print(f"{n:<10} {len(b.calls)}/{b.rpm} ready={b.ready()}")'''
new = '''        import os as _os
        for n, b in buckets.items():
            key = _os.environ.get(PROVIDERS[n]["env"])
            print(f"{n:<10} {len(b.calls)}/{b.rpm:<3} key={'set' if key else 'MISSING':<8} ready={b.ready()}")'''
assert old in src
p.write_text(src.replace(old, new))
print("patched 70_async_router.py: --status now reflects key presence")
