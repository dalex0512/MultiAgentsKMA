import logging

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from config import AGENTS, COLLECTION_NAME, QDRANT_API_KEY, QDRANT_URL

log = logging.getLogger(__name__)


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def count_points_for_agent(client: QdrantClient, agent_id: str) -> int:
    flt = Filter(must=[FieldCondition(key="agent_id", match=MatchValue(value=agent_id))])
    total = 0
    offset = None
    while True:
        pts, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=flt,
            limit=200,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        total += len(pts)
        if offset is None:
            break
    return total


def collection_health() -> dict:
    try:
        client = get_client()
        collections = [c.name for c in client.get_collections().collections]
        exists = COLLECTION_NAME in collections
        info = {}
        total = 0
        if exists:
            coll = client.get_collection(COLLECTION_NAME)
            total = coll.points_count or 0
            info = {
                "status": str(getattr(coll, "status", "ok")),
                "vectors_count": coll.points_count,
            }
        per_agent = {}
        if exists:
            for aid in AGENTS:
                try:
                    per_agent[aid] = count_points_for_agent(client, aid)
                except Exception as e:
                    log.warning("count agent %s: %s", aid, e)
                    per_agent[aid] = -1
        return {
            "ok": True,
            "collection": COLLECTION_NAME,
            "exists": exists,
            "total_points": total,
            "per_agent_points": per_agent,
            "detail": info,
        }
    except Exception as e:
        log.exception("qdrant health")
        return {"ok": False, "error": str(e)}
