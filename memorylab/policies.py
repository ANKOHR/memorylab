"""Six inspectable, deterministic memory policies and their shared interface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


POLICY_DESCRIPTIONS = {
    "full_context": "Keeps every fact event and presents recent events first within budget.",
    "summary": "Keeps one most recent subject-value note per relation, a lossy summary.",
    "token_overlap": "Ranks event text by distinct token overlap, recency, then fact ID.",
    "episodic": "Keeps time-tagged events and prioritizes the queried key's timeline.",
    "structured": "Keeps typed current state with set, correct, and expire operations.",
    "hybrid": "Uses typed state first, then exact event history and overlap fallback.",
}

POLICY_NAMES = tuple(POLICY_DESCRIPTIONS)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    """Return normalized word tokens used by overlap scoring."""
    return _TOKEN_RE.findall(text.casefold())


def token_count(text: str) -> int:
    """Count whitespace-separated context tokens for the hand-checkable budget."""
    return len(text.split())


def fact_text(event: dict[str, Any]) -> str:
    parts = [event.get("subject", ""), event.get("relation", "")]
    if event.get("object") is not None:
        parts.append(event["object"])
    return " ".join(parts)


def key_of(value: dict[str, Any]) -> tuple[str, str]:
    return (str(value.get("subject", "")).casefold(), str(value.get("relation", "")).casefold())


def render_event(event: dict[str, Any]) -> str:
    fields = [event.get("at", ""), event.get("op", ""), event.get("subject", ""), event.get("relation", "")]
    if event.get("object") is not None:
        fields.append(event["object"])
    return " ".join(str(field) for field in fields)


@dataclass(frozen=True)
class ContextItem:
    render: str
    fact_id: str
    order: int
    event: dict[str, Any] | None = None
    value: dict[str, Any] | None = None
    score: int = 0


@dataclass(frozen=True)
class Response:
    answer: str | None
    source_fact_id: str | None
    context_fact_ids: tuple[str, ...]
    context_tokens: int
    query_tokens: int

    @property
    def tokens_used(self) -> int:
        return self.context_tokens + self.query_tokens


def select_within_budget(items: Iterable[ContextItem], token_budget: int) -> list[ContextItem]:
    """Greedily retain prioritized entries that fit the memory-token budget."""
    selected: list[ContextItem] = []
    used = 0
    for item in items:
        cost = token_count(item.render)
        if used + cost <= token_budget:
            selected.append(item)
            used += cost
    return selected


def resolve_events(events: Iterable[dict[str, Any]], key: tuple[str, str]) -> tuple[str | None, str | None]:
    """Apply set-if-absent, unconditional correct, and expire rules in order."""
    current_value: str | None = None
    current_id: str | None = None
    for event in sorted(events, key=lambda entry: entry.get("_order", 0)):
        if key_of(event) != key:
            continue
        op = event["op"]
        if op == "set":
            if current_value is None:
                current_value = event.get("object")
                current_id = event["fact_id"]
        elif op == "correct":
            current_value = event.get("object")
            current_id = event["fact_id"]
        elif op == "expire":
            current_value = None
            current_id = None
        else:
            raise ValueError(f"Unknown fact operation: {op}")
    return current_value, current_id


def _event_item(event: dict[str, Any], order: int, score: int = 0) -> ContextItem:
    return ContextItem(render_event(event), event["fact_id"], order, event=event, score=score)


def _state_item(value: dict[str, Any], order: int) -> ContextItem:
    render = f"{value['subject']} {value['relation']} {value['object']}"
    return ContextItem(render, value["fact_id"], order, value=value)


class MemoryPolicy:
    """Policy protocol: observe facts, inspect memory, answer under a token budget."""

    name = "base"

    def observe(self, event: dict[str, Any]) -> None:
        raise NotImplementedError

    def inspect(self) -> dict[str, Any]:
        raise NotImplementedError

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        raise NotImplementedError


class FullContextPolicy(MemoryPolicy):
    name = "full_context"

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def observe(self, event: dict[str, Any]) -> None:
        self.events.append({**event, "_order": len(self.events)})

    def inspect(self) -> dict[str, Any]:
        return {"type": "full_context", "events": [_public_event(event) for event in self.events]}

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        key = key_of(query)
        prioritized = [_event_item(event, event["_order"]) for event in reversed(self.events)]
        selected = select_within_budget(prioritized, token_budget)
        answer, source = resolve_events((item.event for item in selected if item.event), key)
        return _response(query, selected, answer, source)


class SummaryPolicy(MemoryPolicy):
    name = "summary"

    def __init__(self) -> None:
        self.summary: dict[str, dict[str, Any]] = {}
        self._order = 0

    def observe(self, event: dict[str, Any]) -> None:
        relation = str(event["relation"]).casefold()
        slot = self.summary.get(relation)
        if event["op"] == "expire":
            if slot is not None and str(slot["subject"]).casefold() == str(event["subject"]).casefold():
                del self.summary[relation]
        else:
            same_subject = slot is not None and str(slot["subject"]).casefold() == str(event["subject"]).casefold()
            if event["op"] != "set" or not same_subject:
                self.summary[relation] = {**event, "_order": self._order}
        self._order += 1

    def inspect(self) -> dict[str, Any]:
        return {
            "type": "relation_summary",
            "rule": "one latest subject-value note per relation",
            "entries": [
                {
                    "relation": value["relation"],
                    "subject": value["subject"],
                    "object": value.get("object"),
                    "source_fact_id": value["fact_id"],
                    "at": value["at"],
                }
                for _, value in sorted(self.summary.items())
            ],
        }

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        relation = str(query["relation"]).casefold()
        items: list[ContextItem] = []
        for rel, value in sorted(self.summary.items()):
            render = f"{value['relation']} {value['subject']} {value.get('object', '')}".strip()
            items.append(ContextItem(render, value["fact_id"], value["_order"], value=value))
        selected = select_within_budget(items, token_budget)
        match = next((item for item in selected if str(item.value["relation"]).casefold() == relation), None)
        answer = match.value.get("object") if match is not None and match.value else None
        source = match.fact_id if match is not None else None
        return _response(query, selected, answer, source)


class TokenOverlapPolicy(MemoryPolicy):
    name = "token_overlap"

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def observe(self, event: dict[str, Any]) -> None:
        self.events.append({**event, "_order": len(self.events)})

    def inspect(self) -> dict[str, Any]:
        return {"type": "token_overlap_index", "events": [_public_event(event) for event in self.events]}

    @staticmethod
    def score(query_text: str, event: dict[str, Any]) -> int:
        return len(set(words(query_text)) & set(words(fact_text(event))))

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        ranked = sorted(
            self.events,
            key=lambda event: (
                -self.score(query["text"], event),
                -event["_order"],
                event["fact_id"],
            ),
        )
        items = [_event_item(event, event["_order"], self.score(query["text"], event)) for event in ranked]
        selected = select_within_budget(items, token_budget)
        best = selected[0] if selected else None
        answer: str | None = None
        source: str | None = None
        if best is not None and best.event is not None:
            event = best.event
            if event["op"] != "expire":
                answer = event.get("object")
                source = event["fact_id"]
        return _response(query, selected, answer, source)


class EpisodicPolicy(MemoryPolicy):
    name = "episodic"

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def observe(self, event: dict[str, Any]) -> None:
        self.events.append({**event, "_order": len(self.events)})

    def inspect(self) -> dict[str, Any]:
        return {"type": "time_tagged_event_store", "events": [_public_event(event) for event in self.events]}

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        key = key_of(query)
        ranked = sorted(
            self.events,
            key=lambda event: (
                0 if key_of(event) == key else 1,
                event["_order"],
                event["fact_id"],
            ),
        )
        selected = select_within_budget(
            (_event_item(event, event["_order"]) for event in ranked), token_budget
        )
        answer, source = resolve_events((item.event for item in selected if item.event), key)
        return _response(query, selected, answer, source)


class StructuredPolicy(MemoryPolicy):
    name = "structured"

    def __init__(self) -> None:
        self.state: dict[tuple[str, str], dict[str, Any]] = {}
        self._order = 0

    def observe(self, event: dict[str, Any]) -> None:
        key = key_of(event)
        if event["op"] == "set":
            if key not in self.state:
                self.state[key] = {**event, "_order": self._order}
        elif event["op"] == "correct":
            self.state[key] = {**event, "_order": self._order}
        elif event["op"] == "expire":
            self.state.pop(key, None)
        else:
            raise ValueError(f"Unknown fact operation: {event['op']}")
        self._order += 1

    def inspect(self) -> dict[str, Any]:
        return {
            "type": "typed_state",
            "rules": {"set": "only when absent", "correct": "replace active value", "expire": "remove key"},
            "entries": [
                {
                    "subject": value["subject"],
                    "relation": value["relation"],
                    "object": value["object"],
                    "source_fact_id": value["fact_id"],
                    "at": value["at"],
                }
                for _, value in sorted(self.state.items())
            ],
        }

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        key = key_of(query)
        values = sorted(
            self.state.values(),
            key=lambda value: (0 if key_of(value) == key else 1, key_of(value), value["fact_id"]),
        )
        items = [_state_item(value, value["_order"]) for value in values]
        selected = select_within_budget(items, token_budget)
        match = next((item for item in selected if item.value and key_of(item.value) == key), None)
        answer = match.value.get("object") if match is not None and match.value else None
        source = match.fact_id if match is not None else None
        return _response(query, selected, answer, source)


class HybridPolicy(MemoryPolicy):
    name = "hybrid"

    def __init__(self) -> None:
        self.state = StructuredPolicy()
        self.events: list[dict[str, Any]] = []
        self._order = 0

    def observe(self, event: dict[str, Any]) -> None:
        copied = {**event, "_order": self._order}
        self.events.append(copied)
        self.state.observe(event)
        self._order += 1

    def inspect(self) -> dict[str, Any]:
        return {
            "type": "hybrid",
            "structured": self.state.inspect(),
            "event_index": [_public_event(event) for event in self.events],
        }

    def respond(self, query: dict[str, Any], token_budget: int) -> Response:
        key = key_of(query)
        current = next((value for value in self.state.state.values() if key_of(value) == key), None)
        if current is not None:
            item = _state_item(current, current["_order"])
            selected = select_within_budget([item], token_budget)
            match = selected[0] if selected else None
            answer = match.value.get("object") if match and match.value else None
            source = match.fact_id if match else None
            return _response(query, selected, answer, source)

        exact_history = [event for event in self.events if key_of(event) == key]
        if exact_history:
            prioritized = [_event_item(event, event["_order"]) for event in reversed(exact_history)]
            selected = select_within_budget(prioritized, token_budget)
            answer, source = resolve_events((item.event for item in selected if item.event), key)
            return _response(query, selected, answer, source)

        query_words = set(words(query["text"]))
        ranked = sorted(
            self.events,
            key=lambda event: (
                -len(query_words & set(words(fact_text(event)))),
                -event["_order"],
                event["fact_id"],
            ),
        )
        items = [
            _event_item(event, event["_order"], len(query_words & set(words(fact_text(event)))))
            for event in ranked
        ]
        selected = select_within_budget(items, token_budget)
        best = selected[0] if selected and selected[0].score >= 2 else None
        answer = None
        source = None
        if best and best.event and best.event["op"] != "expire":
            answer, source = best.event.get("object"), best.fact_id
        return _response(query, selected, answer, source)


def _response(
    query: dict[str, Any],
    selected: list[ContextItem],
    answer: str | None,
    source_fact_id: str | None,
) -> Response:
    return Response(
        answer=answer,
        source_fact_id=source_fact_id,
        context_fact_ids=tuple(item.fact_id for item in selected),
        context_tokens=sum(token_count(item.render) for item in selected),
        query_tokens=token_count(query["text"]),
    )


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if not key.startswith("_")}


def create_policy(name: str) -> MemoryPolicy:
    policy_types = {
        "full_context": FullContextPolicy,
        "summary": SummaryPolicy,
        "token_overlap": TokenOverlapPolicy,
        "episodic": EpisodicPolicy,
        "structured": StructuredPolicy,
        "hybrid": HybridPolicy,
    }
    try:
        return policy_types[name]()
    except KeyError as error:
        raise ValueError(f"Unknown policy {name!r}. Choose from: {', '.join(POLICY_NAMES)}") from error


def overlap_rank(query_text: str, events: Iterable[dict[str, Any]]) -> list[tuple[str, int]]:
    """Expose the policy ranking formula for inspection and hand verification."""
    indexed = list(events)
    ranked = sorted(
        indexed,
        key=lambda event: (
            -TokenOverlapPolicy.score(query_text, event),
            -event.get("_order", 0),
            event["fact_id"],
        ),
    )
    return [(event["fact_id"], TokenOverlapPolicy.score(query_text, event)) for event in ranked]
