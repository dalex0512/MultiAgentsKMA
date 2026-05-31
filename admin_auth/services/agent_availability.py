from admin_auth.services.admin_settings import load_settings
from config import AGENT_IDS


def disabled_agent_ids() -> set[str]:
    return set(load_settings().get("disabled_agents") or [])


def active_agent_ids() -> list[str]:
    off = disabled_agent_ids()
    return [a for a in AGENT_IDS if a not in off]


def filter_enabled_agents(agents: list[str]) -> list[str]:
    off = disabled_agent_ids()
    return [a for a in agents if a not in off]
