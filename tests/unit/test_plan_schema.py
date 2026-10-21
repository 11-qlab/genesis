from __future__ import annotations

from agi.reasoning.schemas import Plan, PlanStep


def test_valid_chain() -> None:
    p = Plan(goal="g", steps=[
        PlanStep(id="a", title="A", tool="fs_list", args={"path": "."}),
        PlanStep(id="b", title="B", tool="fs_list", args={"path": "."}, depends_on=["a"]),
    ])
    assert p.validate_graph({"fs_list"}) == []
    order = [s.id for s in p.topo_order()]
    assert order == ["a", "b"]


def test_cycle_rejected() -> None:
    p = Plan(goal="g", steps=[
        PlanStep(id="x", title="X", depends_on=["y"]),
        PlanStep(id="y", title="Y", depends_on=["x"]),
    ])
    assert p.validate_graph(set())


def test_unknown_tool_rejected() -> None:
    p = Plan(goal="g", steps=[PlanStep(id="a", title="A", tool="nope")])
    problems = p.validate_graph({"fs_list"})
    assert any("unknown tool" in m for m in problems)


def test_missing_dependency_rejected() -> None:
    p = Plan(goal="g", steps=[PlanStep(id="a", title="A", depends_on=["zzz"])])
    problems = p.validate_graph(set())
    assert any("unknown step" in m for m in problems)


def test_duplicate_ids_rejected() -> None:
    p = Plan(goal="g", steps=[
        PlanStep(id="a", title="A"),
        PlanStep(id="a", title="B"),
    ])
    problems = p.validate_graph(set())
    assert any("duplicate" in m for m in problems)


def test_topo_order_deterministic() -> None:
    p = Plan(goal="g", steps=[
        PlanStep(id="a", title="A"),
        PlanStep(id="b", title="B"),
        PlanStep(id="c", title="C", depends_on=["a", "b"]),
    ])
    order1 = [s.id for s in p.topo_order()]
    order2 = [s.id for s in p.topo_order()]
    assert order1 == order2
    assert order1[-1] == "c"
