import pytest
from app.graph import CPNEngine, Place, Transition
from app.schemas import MasterState, PlaceName

def test_cpn_basic_routing():
    engine = CPNEngine()
    
    p_start = engine.add_place("start")
    p_middle = engine.add_place("middle")
    p_end = engine.add_place("end", terminal=True)
    
    def action_start(state: MasterState):
        state.retry_count += 1
        return state, "ok"
        
    engine.add_transition(
        "t1",
        source=p_start,
        targets={"ok": p_middle},
        action=action_start
    )
    
    engine.add_transition(
        "t2",
        source=p_middle,
        targets={"finish": p_end},
        action=lambda s: (s, "finish")
    )
    
    state = MasterState(trace_id="123", task_id="456", current_node="start")
    final_state = engine.run(state)
    
    assert final_state.current_node == "end"
    assert final_state.retry_count == 1
    assert final_state.completed is True

def test_cpn_validation():
    engine = CPNEngine()
    p1 = engine.add_place("p1")
    p2 = engine.add_place("p2", terminal=True)
    
    # Missing target place
    engine.add_transition(
        "t1",
        source=p1,
        targets={"ok": Place("nonexistent")},
        action=lambda s: (s, "ok")
    )
    
    issues = engine.validate_net()
    assert len(issues) > 0
    assert "not a registered place" in issues[0]

def test_cpn_deadlock():
    engine = CPNEngine()
    p_start = engine.add_place("start")
    
    # Guard prevents firing
    engine.add_transition(
        "t1",
        source=p_start,
        targets={"ok": p_start},
        action=lambda s: (s, "ok"),
        guard=lambda s: False
    )
    
    state = MasterState(trace_id="123", task_id="456", current_node="start")
    final_state = engine.run(state)
    
    assert final_state.current_node == PlaceName.PERROR.value
    assert "Deadlock" in final_state.error
