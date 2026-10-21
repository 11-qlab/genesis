from __future__ import annotations

from agi.reasoning import Plan, PlanStep, typecheck_plan


def _plan(steps):
    return Plan(goal="g", steps=steps)


def test_simple_plan_typechecks():
    p = _plan([
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}),
    ])
    assert typecheck_plan(p) == []


def test_unknown_tool():
    p = _plan([PlanStep(id="s1", title="t", tool="ghost", args={})])
    errs = typecheck_plan(p)
    assert any("unknown tool" in e.message for e in errs)


def test_wrong_arg_count():
    p = _plan([PlanStep(id="s1", title="t", tool="fs_write",
                        args={"path": "a.txt"})])
    errs = typecheck_plan(p)
    assert errs and "do not match params" in errs[0].message


def test_missing_reference():
    p = _plan([PlanStep(id="s2", title="t", tool="fs_read",
                        args={"path": "$s1.out"})])
    errs = typecheck_plan(p)
    assert errs and "no binding" in errs[0].message


def test_valid_data_flow():
    p = _plan([
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}),
        PlanStep(id="s2", title="t", tool="fs_write",
                 args={"path": "dump.txt", "content": "$s1.out",
                       "mode": "overwrite"}),
    ])
    assert typecheck_plan(p) == []


def test_wrong_type_from_ref():
    # $s1.ok is Bool, but fs_write.content expects Str
    p = _plan([
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}),
        PlanStep(id="s2", title="t", tool="fs_write",
                 args={"path": "x", "content": "$s1.ok", "mode": "overwrite"}),
    ])
    errs = typecheck_plan(p)
    assert any("Str" in e.message and "Bool" in e.message for e in errs)


def test_duplicate_step_id():
    p = _plan([
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}),
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}),
    ])
    errs = typecheck_plan(p)
    assert any("duplicate" in e.message for e in errs)


def test_malformed_reference():
    p = _plan([
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "$garbage"}),
    ])
    errs = typecheck_plan(p)
    assert errs and "malformed" in errs[0].message
