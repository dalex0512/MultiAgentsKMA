import json
import logging
from pathlib import Path

from config import AGENTS, DOCS_ROOT

log = logging.getLogger(__name__)


def load_catalog(agent_id: str) -> dict | None:
    if agent_id != "bieu_mau":
        return None
    cat_path = Path(DOCS_ROOT) / "bieu_mau" / "catalog.json"
    if cat_path.exists():
        return json.loads(cat_path.read_text(encoding="utf-8"))
    return {}


def ingest_file(agent_id: str, path: Path) -> int:
    from ingest_all import ensure_collection, ingest_document

    cfg = AGENTS[agent_id]
    ensure_collection()
    catalog = load_catalog(agent_id)
    return ingest_document(path, agent_id, cfg["folder"], catalog=catalog)


def reindex_agent(agent_id: str) -> int:
    from ingest_all import ensure_collection, ingest_domain

    ensure_collection()
    return ingest_domain(agent_id)


def delete_vectors(source_key: str) -> None:
    from ingest_all import delete_source

    delete_source(source_key)
