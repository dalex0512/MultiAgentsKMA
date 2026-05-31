import logging

from admin_auth.core.config import settings

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(
        settings.LDAP_ENABLED
        and settings.LDAP_SERVER
        and settings.LDAP_USER_BASE
    )


def authenticate(username: str, password: str) -> dict | None:
    """Trả về {email, cn} nếu LDAP OK, None nếu sai."""
    if not is_configured():
        return None

    try:
        import ldap3
    except ImportError:
        log.error("ldap3 chưa cài — pip install ldap3")
        return None

    server = ldap3.Server(
        settings.LDAP_SERVER,
        port=settings.LDAP_PORT,
        use_ssl=settings.LDAP_USE_SSL,
        get_info=ldap3.NONE,
    )

    user_filter = settings.LDAP_USER_FILTER.format(username=username)
    bind_ok = False
    conn = None

    try:
        if settings.LDAP_BIND_DN:
            conn = ldap3.Connection(
                server,
                user=settings.LDAP_BIND_DN,
                password=settings.LDAP_BIND_PASSWORD,
                auto_bind=True,
            )
            conn.search(
                settings.LDAP_USER_BASE,
                user_filter,
                attributes=["dn", settings.LDAP_EMAIL_ATTR, "cn"],
            )
            if not conn.entries:
                return None
            user_dn = conn.entries[0].entry_dn
            conn.unbind()
            conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)
            bind_ok = conn.bound
            if bind_ok:
                email = str(getattr(conn.entries[0], settings.LDAP_EMAIL_ATTR, "") or "")
                cn = str(getattr(conn.entries[0], "cn", username) or username)
                return {"email": email, "cn": cn, "username": username}
        else:
            user_dn_guess = f"uid={username},{settings.LDAP_USER_BASE}"
            conn = ldap3.Connection(server, user=user_dn_guess, password=password, auto_bind=True)
            bind_ok = conn.bound
            if bind_ok:
                return {"email": "", "cn": username, "username": username}
    except Exception as e:
        log.warning("LDAP auth failed for %s: %s", username, e)
        return None
    finally:
        if conn:
            try:
                conn.unbind()
            except Exception:
                pass

    return None
