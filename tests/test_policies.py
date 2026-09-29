from __future__ import annotations

from memorylab.policies import (
    EpisodicPolicy,
    FullContextPolicy,
    StructuredPolicy,
    SummaryPolicy,
    TokenOverlapPolicy,
    create_policy,
    overlap_rank,
)


def fact(fact_id, at, op, subject, relation, object_value=None):
    value = {
        "type": "fact",
        "fact_id": fact_id,
        "at": at,
        "op": op,
        "subject": subject,
        "relation": relation,
    }
    if object_value is not None:
        value["object"] = object_value
    return value


def query(subject="Mira", relation="team", text="Mira team?"):
    return {"type": "query", "query_id": "q", "subject": subject, "relation": relation, "text": text}


def test_full_context_retains_and_resolves_event_history():
    policy = FullContextPolicy()
    policy.observe(fact("f1", "t1", "set", "Mira", "team", "Blue"))
    policy.observe(fact("f2", "t2", "correct", "Mira", "team", "Green"))
    response = policy.respond(query(), 100)
    assert response.answer == "Green"
    assert response.source_fact_id == "f2"
    assert policy.inspect()["type"] == "full_context"
    assert [item["fact_id"] for item in policy.inspect()["events"]] == ["f1", "f2"]


def test_summary_keeps_one_latest_note_per_relation_and_exposes_collision():
    policy = SummaryPolicy()
    policy.observe(fact("f1", "t1", "set", "Mira", "team", "Blue"))
    policy.observe(fact("f2", "t2", "set", "Noah", "team", "Red"))
    assert policy.inspect()["entries"] == [
        {"relation": "team", "subject": "Noah", "object": "Red", "source_fact_id": "f2", "at": "t2"}
    ]
    response = policy.respond(query(), 100)
    assert response.answer == "Red"
    assert response.source_fact_id == "f2"


def test_summary_obeys_set_for_same_subject_and_replaces_on_correct():
    policy = SummaryPolicy()
    policy.observe(fact("f1", "t1", "set", "Mira", "team", "Blue"))
    policy.observe(fact("f2", "t2", "set", "Mira", "team", "Red"))
    assert policy.respond(query(), 100).answer == "Blue"
    policy.observe(fact("f3", "t3", "correct", "Mira", "team", "Green"))
    assert policy.respond(query(), 100).answer == "Green"


def test_token_overlap_formula_counts_unique_shared_words_then_ties():
    events = [
        {**fact("z9", "t1", "set", "Mira", "team", "Blue"), "_order": 5},
        {**fact("a1", "t1", "set", "Mira", "team", "Green"), "_order": 5},
        {**fact("b2", "t2", "set", "Nia", "badge", "team"), "_order": 7},
    ]
    assert overlap_rank("Mira team Mira", events) == [("a1", 2), ("z9", 2), ("b2", 1)]
    policy = TokenOverlapPolicy()
    for event in events:
        policy.observe({key: value for key, value in event.items() if key != "_order"})
    response = policy.respond(query(), 100)
    assert response.source_fact_id == "a1"
    assert response.answer == "Green"


def test_episodic_policy_keeps_time_tags_and_prioritizes_exact_timeline():
    policy = EpisodicPolicy()
    policy.observe(fact("f1", "t1", "set", "Other", "team", "Gold"))
    policy.observe(fact("f2", "t2", "set", "Mira", "team", "Blue"))
    response = policy.respond(query(), 100)
    assert response.answer == "Blue"
    assert response.context_fact_ids[0] == "f2"
    assert [event["at"] for event in policy.inspect()["events"]] == ["t1", "t2"]


def test_structured_set_correct_expire_rules_and_inspectable_state():
    policy = StructuredPolicy()
    policy.observe(fact("f1", "t1", "set", "Mira", "team", "Blue"))
    policy.observe(fact("f2", "t2", "set", "Mira", "team", "Red"))
    assert policy.respond(query(), 100).answer == "Blue"
    policy.observe(fact("f3", "t3", "correct", "Mira", "team", "Green"))
    assert policy.respond(query(), 100).answer == "Green"
    assert policy.inspect()["entries"][0]["source_fact_id"] == "f3"
    policy.observe(fact("f4", "t4", "expire", "Mira", "team"))
    assert policy.inspect()["entries"] == []
    assert policy.respond(query(), 100).answer is None


def test_structured_set_after_expire_creates_a_new_active_value():
    policy = StructuredPolicy()
    policy.observe(fact("f1", "t1", "set", "Mira", "team", "Blue"))
    policy.observe(fact("f2", "t2", "expire", "Mira", "team"))
    policy.observe(fact("f3", "t3", "set", "Mira", "team", "Gold"))
    assert policy.respond(query(), 100).answer == "Gold"


def test_all_policy_names_construct_an_inspectable_memory():
    for name in ("full_context", "summary", "token_overlap", "episodic", "structured", "hybrid"):
        policy = create_policy(name)
        assert policy.inspect()
        assert callable(policy.observe)
        assert callable(policy.respond)


def test_memory_budget_caps_context_but_counts_query_tokens():
    policy = FullContextPolicy()
    policy.observe(fact("f1", "t1", "set", "Mira", "team", "Blue"))
    response = policy.respond(query(text="Mira team?"), 3)
    assert response.context_tokens == 0
    assert response.query_tokens == 2
    assert response.tokens_used == 2
    assert response.answer is None
