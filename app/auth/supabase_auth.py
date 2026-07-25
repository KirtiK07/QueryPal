import os
from supabase import create_client, Client
from sqlalchemy import text
from app.database.db import get_engine, get_direct_engine


class AuthError(Exception):
    pass


_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise AuthError("SUPABASE_URL / SUPABASE_ANON_KEY are not configured.")
        _client = create_client(url, key)
    return _client


def _schema_name_for(user_id: str) -> str:
    # user_id is always a UUID issued by Supabase Auth, never user-controllable
    # text, so this is safe to interpolate directly into DDL below.
    return "user_" + user_id.replace("-", "")[:12]


def _provision_profile(user_id: str, email: str) -> str:
    """Creates the user's private schema and profiles row if they don't already
    exist yet. Safe to call on every login, not just signup, since a fresh
    account may not have a profiles row until email confirmation completes."""
    schema_name = _schema_name_for(user_id)
    engine = get_direct_engine()
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        conn.execute(text("""
            INSERT INTO public.profiles (id, email, role, schema_name)
            VALUES (:id, :email, 'user', :schema_name)
            ON CONFLICT (id) DO NOTHING
        """), {"id": user_id, "email": email, "schema_name": schema_name})
        conn.commit()
    return schema_name


def get_profile(user_id: str) -> dict | None:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT email, role, schema_name FROM public.profiles WHERE id = :id"
        ), {"id": user_id}).mappings().first()
    return dict(row) if row else None


def sign_up(email: str, password: str) -> dict:
    client = get_client()
    try:
        response = client.auth.sign_up({"email": email, "password": password})
    except Exception as e:
        raise AuthError(str(e))

    if not response.user:
        raise AuthError("Sign up failed — no user returned.")

    schema_name = _provision_profile(response.user.id, email)

    if response.session:
        return {
            "id": response.user.id,
            "email": email,
            "role": "user",
            "schema_name": schema_name,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "email_confirmation_pending": False,
        }
    # Project has "Confirm email" enabled in Supabase Auth settings — no
    # session is issued until the user clicks the confirmation link.
    return {"email_confirmation_pending": True}


def sign_in(email: str, password: str) -> dict:
    client = get_client()
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as e:
        raise AuthError("Incorrect email or password.") from e

    if not response.user or not response.session:
        raise AuthError("Incorrect email or password.")

    profile = get_profile(response.user.id) or {
        "email": email,
        "role": "user",
        "schema_name": _provision_profile(response.user.id, email),
    }

    return {
        "id": response.user.id,
        "email": profile["email"],
        "role": profile["role"],
        "schema_name": profile["schema_name"],
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
    }


def restore_session(refresh_token: str) -> dict | None:
    """Silently re-establishes a session from a cookie-stored refresh token."""
    client = get_client()
    try:
        response = client.auth.refresh_session(refresh_token)
    except Exception:
        return None

    if not response.user or not response.session:
        return None

    profile = get_profile(response.user.id)
    if not profile:
        return None

    return {
        "id": response.user.id,
        "email": profile["email"],
        "role": profile["role"],
        "schema_name": profile["schema_name"],
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
    }


def sign_out():
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
