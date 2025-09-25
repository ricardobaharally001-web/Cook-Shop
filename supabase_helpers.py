import os
import io
from datetime import datetime
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
    res = sb.table("menu_items").select("id,name,description,price,image_url,category_id,created_at").order("created_at", desc=True).execute()
    return res.data or []


def list_items_for_category(category_id: int):
    sb = supabase()
    res = sb.table("menu_items").select("id,name,description,price,image_url,category_id,created_at").eq("category_id", category_id).order("name").execute()
    return res.data or []


def create_item(category_id: int, name: str, description: str | None, price: float | None, image_url: str | None = None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Item name is required")
    sb = supabase()
    payload = {
        "category_id": int(category_id),
        "name": name,
        "description": (description or "").strip() or None,
        "price": float(price) if price not in (None, "") else None,
        "image_url": (image_url or "").strip() or None,
    }
    sb.table("menu_items").insert(payload).execute()


def get_item(item_id: int):
    sb = supabase()
    res = sb.table("menu_items").select("id,name,description,price,image_url,category_id").eq("id", int(item_id)).limit(1).execute()
    if res.data:
        return res.data[0]
    return None

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


# --- Assets upload (logo) ---

def _public_url(bucket: str, path: str) -> str:
    url, _ = _get_env()
    return f"{url}/storage/v1/object/public/{bucket}/{path}"


def upload_logo_to_supabase(file_storage) -> str:
    """Upload a logo to the assets bucket and return its public URL."""
    filename = file_storage.filename or "logo.png"
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "png").lower()
    key = f"branding/logo_{stamp}.{ext}"
    data = file_storage.read()
    file_storage.seek(0)
    client = supabase()
    mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
    # Try multiple call signatures for compatibility
    last_err = None
    try:
        client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
            path=key,
            file=data,
            file_options={"contentType": mime, "cacheControl": "3600", "upsert": True},
        )
    except Exception as e_a:
        last_err = e_a
        try:
            client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
                path=key,
                file=data,
                file_options={"contentType": mime, "cacheControl": "3600"},
                upsert=True,
            )
        except Exception as e_b:
            last_err = e_b
            try:
                client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
                    path=key,
                    file=io.BytesIO(data),
                    file_options={"contentType": mime, "cacheControl": "3600"},
                    upsert=True,
                )
            except Exception as e_c:
                last_err = e_c
                raise RuntimeError(f"Supabase upload failed: {last_err}")
    return _public_url(SUPABASE_ASSETS_BUCKET, key)


def upload_item_image(file_storage) -> str:
    """Upload an item image to the assets bucket and return public URL."""
    filename = file_storage.filename or "item.png"
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "png").lower()
    key = f"items/item_{stamp}.{ext}"
    data = file_storage.read()
    file_storage.seek(0)
    client = supabase()
    mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
    try:
        client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
            path=key,
            file=data,
            file_options={"contentType": mime, "cacheControl": "3600", "upsert": True},
        )
    except Exception:
        client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
            path=key,
            file=io.BytesIO(data),
            file_options={"contentType": mime, "cacheControl": "3600"},
            upsert=True,
        )
    return _public_url(SUPABASE_ASSETS_BUCKET, key)
