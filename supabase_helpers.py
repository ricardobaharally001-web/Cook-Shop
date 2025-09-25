import os
from supabase import create_client

# Reuse the same pattern as take-2-main for env + client
SUPABASE_ASSETS_BUCKET = os.environ.get("SUPABASE_ASSETS_BUCKET", "assets")

_client = None

def _get_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    return url, key

def supabase():
    global _client
    if _client is None:
        url, key = _get_env()
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or key env vars")
        _client = create_client(url, key)
    return _client

# --- Categories ---

def list_categories():
    sb = supabase()
    res = sb.table("menu_categories").select("id,name,created_at").order("name").execute()
    return res.data or []

def create_category(name: str):
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name is required")
    sb = supabase()
    # ignore unique violation by upsert
    try:
        sb.table("menu_categories").insert({"name": name}).execute()
    except Exception:
        # last resort: upsert style if supported
        try:
            sb.table("menu_categories").upsert({"name": name}).execute()
        except Exception as e:
            raise e

# --- Items ---

def list_items():
    sb = supabase()
    res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").order("created_at", desc=True).execute()
    return res.data or []


def list_items_for_category(category_id: int):
    sb = supabase()
    res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").eq("category_id", category_id).order("name").execute()
    return res.data or []


def create_item(category_id: int, name: str, description: str | None, price: float | None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Item name is required")
    sb = supabase()
    payload = {
        "category_id": int(category_id),
        "name": name,
        "description": (description or "").strip() or None,
        "price": float(price) if price not in (None, "") else None,
    }
    sb.table("menu_items").insert(payload).execute()

# --- Site settings (optional, mirrored) ---

def get_site_setting(key: str):
    try:
        sb = supabase()
    except Exception:
        return None
    try:
        res = sb.table("site_settings").select("value").eq("key", key).limit(1).execute()
        if res.data:
            return (res.data or [{}])[0].get("value")
    except Exception:
        return None
    return None


def set_site_setting(key: str, value: str):
    sb = supabase()
    try:
        sb.table("site_settings").upsert({"key": key, "value": value}).execute()
    except Exception:
        # Fallback to insert
        sb.table("site_settings").insert({"key": key, "value": value}).execute()
