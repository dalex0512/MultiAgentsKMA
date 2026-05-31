"""
Sau vector search: gom child hit → parent context (dedup), tương thích Qc prefetch.
"""

from __future__ import annotations

import logging

from config import PARENT_CHILD_AGENTS, PARENT_RETRIEVE_MAX

log = logging.getLogger(__name__)


def uses_parent_child_retrieval(agent_id: str | None) -> bool:
    return bool(agent_id) and agent_id in PARENT_CHILD_AGENTS


def collapse_child_hits_to_parents(
    docs: list[dict],
    *,
    max_parents: int | None = None,
) -> list[dict]:
    """
    - Child (chunk_role=child): giữ hit score cao nhất mỗi parent_id, text → parent_text.
    - Flat (chunk_role=flat hoặc thiếu parent): giữ nguyên, dedup theo _doc_key.
    """
    if not docs:
        return docs

    cap = max_parents if max_parents is not None else PARENT_RETRIEVE_MAX
    best_by_parent: dict[str, dict] = {}
    parent_order: list[str] = []
    flat_docs: list[dict] = []
    seen_flat: set[tuple] = set()

    for d in docs:
        role = (d.get("chunk_role") or "flat").strip().lower()
        pid = (d.get("parent_id") or "").strip()
        parent_text = (d.get("parent_text") or "").strip()
        score = float(d.get("_rank_score", d.get("score", 0.0)))

        if role == "child" and pid and parent_text:
            prev = best_by_parent.get(pid)
            if prev is None or score > float(prev.get("_rank_score", prev.get("score", 0))):
                best_by_parent[pid] = {
                    **d,
                    "text": parent_text,
                    "child_match_text": (d.get("text") or "")[:300],
                    "_rank_score": score,
                    "score": round(score, 4),
                }
                if pid not in parent_order:
                    parent_order.append(pid)
            continue

        key = _flat_doc_key(d)
        if key in seen_flat:
            continue
        seen_flat.add(key)
        flat_docs.append(d)

    parents = [best_by_parent[pid] for pid in parent_order if pid in best_by_parent]
    parents.sort(key=lambda x: float(x.get("_rank_score", x.get("score", 0))), reverse=True)

    merged = parents + flat_docs
    if len(merged) > cap:
        merged = merged[:cap]
        log.debug(
            "[retrieval:parent-child] collapsed to %s parent(s) (cap=%s)",
            min(len(parents), cap),
            cap,
        )
    return merged


def _flat_doc_key(d: dict) -> tuple:
    return (
        d.get("source", ""),
        d.get("page", 0),
        (d.get("text") or "")[:120],
    )
