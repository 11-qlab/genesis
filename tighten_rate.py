import os, sys, subprocess, getpass
from openai import OpenAI
from pathlib import Path

if not os.environ.get("GROQ_API_KEY"):
    sys.exit("export GROQ_API_KEY first")
client = OpenAI(base_url="https://api.groq.com/openai/v1",
                api_key=os.environ["GROQ_API_KEY"], timeout=90)

PROMPT = ("Write a Python function approximately_equal(a,b,rel=1e-9) returning True if a and b are equal "
          "up to relative AND absolute tolerance. Handle zero safely. Return ONLY executable code.")
TEST = ("assert approximately_equal(0.1+0.2,0.3)\n"
        "assert approximately_equal(0.0,1e-12)\n"
        "assert approximately_equal(1.0,1.0)\n"
        "assert not approximately_equal(1.0,2.0)\n"
        "assert not approximately_equal(1e-9,1e9)\nprint('PASS')")

K = 40
passes = valid = 0
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
        Path("/tmp/t.py").write_text(code + "\n\n" + TEST)
        pr = subprocess.run([sys.executable, "/tmp/t.py"], capture_output=True, text=True, timeout=15)
        if pr.returncode == 0 and "PASS" in pr.stdout: passes += 1
    except Exception as e:
        print("err:", e, file=sys.stderr)
    if (i+1) % 10 == 0:
        print(str(i+1) + "/" + str(K) + "  pass=" + str(passes) + "/" + str(valid))

if valid:
    print("\nFinal: " + str(passes) + "/" + str(valid) + " = " + str(round(passes/valid, 3)))
