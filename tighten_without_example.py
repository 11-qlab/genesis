import os, sys, subprocess
from openai import OpenAI
from pathlib import Path

if not os.environ.get("GROQ_API_KEY"):
    sys.exit("export GROQ_API_KEY first")
client = OpenAI(base_url="https://api.groq.com/openai/v1",
                api_key=os.environ["GROQ_API_KEY"], timeout=90)

# Rule stated, but NO example
PROMPT = (
    "Write a Python function merge_intervals(intervals) that merges overlapping closed intervals "
    "AND intervals whose endpoints touch (the end of one equals the start of the next). "
    "Empty list returns []. Return ONLY executable code."
)
TEST = (
    "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]\n"
    "assert merge_intervals([])==[]\n"
    "assert merge_intervals([[1,4],[4,5]])==[[1,5]]\n"
    "print('PASS')"
)

K = 20
passed = valid = 0
for i in range(K):
    try:
        r = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role":"system","content":"Return ONLY executable Python."},
                      {"role":"user","content":PROMPT}],
            temperature=0.0, max_tokens=1500)
        code = (r.choices[0].message.content or "").strip()
        if code.startswith("```"):
            code = "\n".join(code.split("\n")[1:]).rstrip().rstrip("`").strip()
        if not code: continue
        valid += 1
        p = Path("/tmp/twe.py")
        p.write_text(code + "\n\n" + TEST)
        pr = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
        if pr.returncode == 0 and "PASS" in pr.stdout:
            passed += 1
    except Exception as e:
        print("err:", e, file=sys.stderr)
    if (i+1) % 10 == 0:
        print(str(i+1) + "/" + str(K) + "  pass=" + str(passed) + "/" + str(valid))

print("\nFinal: " + str(passed) + "/" + str(valid) +
      " = " + str(round(passed/valid, 3) if valid else 0))
