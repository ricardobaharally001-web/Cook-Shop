import os
import json
import io
from datetime import datetime
from supabase import create_client

# Reuse the same pattern as take-2-main for env + client
SUPABASE_ASSETS_BUCKET = os.environ.get("SUPABASE_ASSETS_BUCKET", "assets")

_client = None

BASE_DIR = os.path.dirname(__file__)
PRODUCTS_FILE = os.path.join(BASE_DIR, "products.json")
CATEGORIES_FILE = os.path.join(BASE_DIR, "categories.json")

# Cache timestamps for performance
_products_cache = None
_products_cache_time = 0
_categories_cache = None
_categories_cache_time = 0
CACHE_DURATION = 30  # seconds

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

def _load_json_cache():
    """Load data from JSON cache with timestamp checking"""
    global _products_cache, _products_cache_time, _categories_cache, _categories_cache_time
    current_time = datetime.now().timestamp()
    
    # Load products cache if expired
    if _products_cache is None or (current_time - _products_cache_time) > CACHE_DURATION:
        if os.path.exists(PRODUCTS_FILE):
            try:
                with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                    _products_cache = json.load(f)
                    _products_cache_time = current_time
            except Exception:
                _products_cache = []
        else:
            _products_cache = []
    
    # Load categories cache if expired
    if _categories_cache is None or (current_time - _categories_cache_time) > CACHE_DURATION:
        if os.path.exists(CATEGORIES_FILE):
            try:
                with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
                    _categories_cache = json.load(f)
                    _categories_cache_time = current_time
            except Exception:
                _categories_cache = [{"id": 1, "name": "All", "slug": "all"}]
        else:
            _categories_cache = [{"id": 1, "name": "All", "slug": "all"}]
    
    return _products_cache, _categories_cache

def _save_json_cache():
    """Save data to JSON cache files"""
    try:
        # Save products
        if _products_cache:
            with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(_products_cache, f, indent=2, default=str)
        
        # Save categories
        if _categories_cache:
            with open(CATEGORIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(_categories_cache, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving JSON cache: {e}")

# --- Categories ---

def list_categories():
    """Load categories from JSON cache first, then fallback to Supabase."""
    # Try JSON cache first
    products, categories = _load_json_cache()
    if categories:
        return categories
    
    # Fallback to Supabase
    try:
        sb = supabase()
        res = sb.table("menu_categories").select("id,name,created_at").order("name").execute()
        data = res.data or []
        
        # Update cache
        global _categories_cache
        _categories_cache = data
        _categories_cache_time = datetime.now().timestamp()
        
        return data
    except Exception as e:
        print(f"Error loading categories from Supabase: {e}")
        return [{"id": 1, "name": "All", "slug": "all"}]

def create_category(name: str):
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name is required")
    
    # Update JSON cache first
    products, categories = _load_json_cache()
    new_id = max([c.get('id', 0) for c in categories] + [0]) + 1
    new_category = {"id": new_id, "name": name, "slug": name.lower().replace(' ', '-')}
    categories.append(new_category)
    
    # Save to cache
    global _categories_cache
    _categories_cache = categories
    _categories_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also save to Supabase
    try:
        sb = supabase()
        # ignore unique violation by upsert
        try:
            sb.table("menu_categories").insert({"name": name}).execute()
        except Exception:
            # last resort: upsert style if supported
            try:
                sb.table("menu_categories").upsert({"name": name}).execute()
            except Exception as e:
                print(f"Error saving category to Supabase: {e}")
    except Exception as e:
        print(f"Supabase not available for category creation: {e}")

def update_category(category_id: int, name: str):
    # Update JSON cache first
    products, categories = _load_json_cache()
    for cat in categories:
        if cat.get('id') == category_id:
            cat['name'] = (name or "").strip()
            cat['slug'] = name.lower().replace(' ', '-')
            break
    
    # Save to cache
    global _categories_cache
    _categories_cache = categories
    _categories_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also update Supabase
    try:
        sb = supabase()
        sb.table("menu_categories").update({"name": (name or "").strip()}).eq("id", int(category_id)).execute()
    except Exception as e:
        print(f"Error updating category in Supabase: {e}")

def delete_category(category_id: int):
    # Update JSON cache first
    products, categories = _load_json_cache()
    categories = [c for c in categories if c.get('id') != category_id]
    
    # Save to cache
    global _categories_cache
    _categories_cache = categories
    _categories_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also delete from Supabase
    try:
        sb = supabase()
        sb.table("menu_categories").delete().eq("id", int(category_id)).execute()
    except Exception as e:
        print(f"Error deleting category from Supabase: {e}")

# --- Items ---

def list_items():
    """Load items from JSON cache first, then fallback to Supabase."""
    # Try JSON cache first
    products, categories = _load_json_cache()
    if products:
        return products
    
    # Fallback to Supabase
    try:
        sb = supabase()
        try:
            res = sb.table("menu_items").select("id,name,description,price,image_url,quantity,category_id,created_at").order("created_at", desc=True).execute()
            data = res.data or []
        except Exception:
            # Fallback for older schema without image_url
            res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").order("created_at", desc=True).execute()
            data = res.data or []
        
        # Update cache
        global _products_cache
        _products_cache = data
        _products_cache_time = datetime.now().timestamp()
        
        return data
    except Exception as e:
        print(f"Error loading items from Supabase: {e}")
        return []


def list_items_for_category(category_id: int):
    """Load items for a specific category from JSON cache first, then fallback to Supabase."""
    # Try JSON cache first
    products, categories = _load_json_cache()
    if products:
        return [item for item in products if item.get('category_id') == category_id]
    
    # Fallback to Supabase
    try:
        sb = supabase()
        try:
            res = sb.table("menu_items").select("id,name,description,price,image_url,quantity,category_id,created_at").eq("category_id", category_id).order("name").execute()
            data = res.data or []
        except Exception:
            res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").eq("category_id", category_id).order("name").execute()
            data = res.data or []
        
        return data
    except Exception as e:
        print(f"Error loading items for category from Supabase: {e}")
        return []


def create_item(category_id: int, name: str, description: str | None, price: float | None, image_url: str | None = None, quantity: int | None = None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Item name is required")
    
    # Update JSON cache first
    products, categories = _load_json_cache()
    new_id = max([p.get('id', 0) for p in products] + [0]) + 1
    new_item = {
        "id": new_id,
        "category_id": int(category_id),
        "name": name,
        "description": (description or "").strip() or None,
        "price": float(price) if price not in (None, "") else None,
        "image_url": (image_url or "").strip() or None,
        "quantity": int(quantity) if quantity not in (None, "") else 0,
        "created_at": datetime.utcnow().isoformat()
    }
    products.append(new_item)
    
    # Save to cache
    global _products_cache
    _products_cache = products
    _products_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also save to Supabase
    try:
        sb = supabase()
        payload = {
            "category_id": int(category_id),
            "name": name,
            "description": (description or "").strip() or None,
            "price": float(price) if price not in (None, "") else None,
            "image_url": (image_url or "").strip() or None,
        }
        if quantity not in (None, ""):
            try:
                payload["quantity"] = int(quantity)
            except Exception:
                pass
        sb.table("menu_items").insert(payload).execute()
    except Exception as e:
        print(f"Error saving item to Supabase: {e}")


def get_item(item_id: int):
    """Get a single item from JSON cache first, then fallback to Supabase."""
    # Try JSON cache first
    products, categories = _load_json_cache()
    for item in products:
        if item.get('id') == item_id:
            return item
    
    # Fallback to Supabase
    try:
        sb = supabase()
        try:
            res = sb.table("menu_items").select("id,name,description,price,image_url,quantity,category_id").eq("id", int(item_id)).limit(1).execute()
        except Exception:
            res = sb.table("menu_items").select("id,name,description,price,category_id").eq("id", int(item_id)).limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"Error getting item from Supabase: {e}")
    return None


def update_item(item_id: int, name: str, description: str | None, price: float | None, image_url: str | None, quantity: int | None = None):
    # Update JSON cache first
    products, categories = _load_json_cache()
    for item in products:
        if item.get('id') == item_id:
            item['name'] = (name or "").strip()
            item['description'] = (description or "").strip() or None
            item['price'] = float(price) if price not in (None, "") else None
            item['image_url'] = (image_url or "").strip() or None
            if quantity is not None:
                item['quantity'] = int(quantity) if quantity else 0
            break
    
    # Save to cache
    global _products_cache
    _products_cache = products
    _products_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also update Supabase
    try:
        sb = supabase()
        payload = {
            "name": (name or "").strip(),
            "description": (description or "").strip() or None,
            "price": float(price) if price not in (None, "") else None,
            "image_url": (image_url or "").strip() or None,
        }
        if quantity not in (None, ""):
            try:
                payload["quantity"] = int(quantity)
            except Exception:
                pass
        sb.table("menu_items").update(payload).eq("id", int(item_id)).execute()
    except Exception as e:
        print(f"Error updating item in Supabase: {e}")


def delete_item(item_id: int):
    # Update JSON cache first
    products, categories = _load_json_cache()
    products = [p for p in products if p.get('id') != item_id]
    
    # Save to cache
    global _products_cache
    _products_cache = products
    _products_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also delete from Supabase
    try:
        sb = supabase()
        sb.table("menu_items").delete().eq("id", int(item_id)).execute()
    except Exception as e:
        print(f"Error deleting item from Supabase: {e}")

# --- Inventory helpers ---

def set_item_quantity(item_id: int, quantity: int):
    sb = supabase()
    try:
        sb.table("menu_items").update({"quantity": int(quantity)}).eq("id", int(item_id)).execute()
    except Exception as e:
        print(f"Error updating quantity in Supabase: {e}")

def change_item_quantity(item_id: int, delta: int):
    sb = supabase()
    try:
        res = sb.table("menu_items").select("quantity").eq("id", int(item_id)).limit(1).execute()
        if res.data:
            current = int(res.data[0].get("quantity", 0))
            sb.table("menu_items").update({"quantity": max(0, current + int(delta))}).eq("id", int(item_id)).execute()
    except Exception as e:
        print(f"Error updating quantity in Supabase: {e}")

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
                # Minimal call: no file_options, no upsert
                client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
                    path=key,
                    file=data,
                )
            except Exception as e_c:
                last_err = e_c
                try:
                    # BytesIO minimal
                    client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
                        path=key,
                        file=io.BytesIO(data),
                    )
                except Exception as e_d:
                    last_err = e_d
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
        try:
            client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
                path=key,
                file=data,
            )
        except Exception:
            client.storage.from_(SUPABASE_ASSETS_BUCKET).upload(
                path=key,
                file=io.BytesIO(data),
            )
    return _public_url(SUPABASE_ASSETS_BUCKET, key)
