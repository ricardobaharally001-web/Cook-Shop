import os
import json
import io
import tempfile
from datetime import datetime
from supabase import create_client

# Production-ready environment variables
SUPABASE_ASSETS_BUCKET = os.environ.get("SUPABASE_ASSETS_BUCKET", "assets")

_client = None

# Use /tmp directory for JSON cache on Render (writable)
BASE_DIR = os.path.dirname(__file__)
PRODUCTS_FILE = os.path.join(tempfile.gettempdir(), "products_cache.json")
CATEGORIES_FILE = os.path.join(tempfile.gettempdir(), "categories_cache.json")

# Cache timestamps for performance
_products_cache = None
_products_cache_time = 0
_categories_cache = None
_categories_cache_time = 0
CACHE_DURATION = 60  # seconds (increased for production)

# Production environment detection
IS_PRODUCTION = os.environ.get("RENDER", "false").lower() == "true"

# Required environment variables with validation
def _get_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        if IS_PRODUCTION:
            raise RuntimeError(
                "Missing required environment variables: SUPABASE_URL and SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY. "
                "Please check your Render environment variables."
            )
        else:
            print("WARNING: Missing Supabase credentials. App will run in local-only mode.")
            return None, None
    
    return url, key

def supabase():
    global _client
    if _client is None:
        url, key = _get_env()
        if not url or not key:
            raise RuntimeError("Supabase credentials not available")
        _client = create_client(url, key)
    return _client

def _save_json_cache():
    """Save data to JSON cache files"""
    global _products_cache, _categories_cache
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
    """Load categories from Supabase directly."""
    global _categories_cache, _categories_cache_time
    
    try:
        sb = supabase()
        res = sb.table("menu_categories").select("id,name,created_at").order("name").execute()
        data = res.data or []
        
        # Update cache
        _categories_cache = data
        _categories_cache_time = datetime.now().timestamp()
        
        return data
    except Exception as e:
        print(f"Error loading categories from Supabase: {e}")
        # Return cache if available
        if _categories_cache:
            return _categories_cache
        return [{"id": 1, "name": "All", "slug": "all"}]

def create_category(name: str):
    global _categories_cache, _categories_cache_time
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name is required")
    
    # Save to Supabase first
    try:
        sb = supabase()
        res = sb.table("menu_categories").insert({"name": name}).execute()
        
        if res.data:
            new_category = res.data[0]
            # Update cache
            if _categories_cache is None:
                _categories_cache = []
            _categories_cache.append(new_category)
            _categories_cache_time = datetime.now().timestamp()
            _save_json_cache()
            return new_category
    except Exception as e:
        print(f"Error saving category to Supabase: {e}")
        raise e

def update_category(category_id: int, name: str):
    global _categories_cache, _categories_cache_time
    
    # Update Supabase first
    try:
        sb = supabase()
        res = sb.table("menu_categories").update({"name": (name or "").strip()}).eq("id", int(category_id)).execute()
        
        # Update cache
        if _categories_cache:
            for cat in _categories_cache:
                if cat.get('id') == int(category_id):
                    cat['name'] = (name or "").strip()
                    break
        
        _categories_cache_time = datetime.now().timestamp()
        _save_json_cache()
        
        return True
    except Exception as e:
        print(f"Error updating category in Supabase: {e}")
        raise e

def delete_category(category_id: int):
    global _categories_cache, _categories_cache_time
    
    # Delete from Supabase first
    try:
        sb = supabase()
        sb.table("menu_categories").delete().eq("id", int(category_id)).execute()
        
        # Update cache
        if _categories_cache:
            _categories_cache = [c for c in _categories_cache if c.get('id') != int(category_id)]
        
        _categories_cache_time = datetime.now().timestamp()
        _save_json_cache()
        
        return True
    except Exception as e:
        print(f"Error deleting category from Supabase: {e}")
        raise e

# --- Items ---

def list_items():
    """Load items from Supabase directly."""
    global _products_cache, _products_cache_time
    
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
        _products_cache = data
        _products_cache_time = datetime.now().timestamp()
        
        return data
    except Exception as e:
        print(f"Error loading items from Supabase: {e}")
        # Return cache if available
        if _products_cache:
            return _products_cache
        return []

def list_items_for_category(category_id: int):
    """Load items for a specific category from Supabase directly."""
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
        # Return filtered cache if available
        if _products_cache:
            return [item for item in _products_cache if item.get('category_id') == category_id]
        return []

def create_item(category_id: int, name: str, description: str | None, price: float | None, image_url: str | None = None, quantity: int | None = None):
    global _products_cache, _products_cache_time
    
    name = (name or "").strip()
    if not name:
        raise ValueError("Item name is required")
    
    # Save to Supabase first (primary data store)
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
        
        # Insert into Supabase
        res = sb.table("menu_items").insert(payload).execute()
        
        # Get the created item (with ID from Supabase)
        if res.data:
            new_item = res.data[0]
            
            # Update cache
            if _products_cache is None:
                _products_cache = []
            _products_cache.append(new_item)
            _products_cache_time = datetime.now().timestamp()
            _save_json_cache()
            
            return new_item
        
    except Exception as e:
        print(f"Error saving item to Supabase: {e}")
        raise e

def get_item(item_id: int):
    """Get a single item from Supabase directly for accuracy."""
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
        # Fallback to cache
        if _products_cache:
            for item in _products_cache:
                if item.get('id') == int(item_id):
                    return item
    return None

def update_item(item_id: int, name: str, description: str | None, price: float | None, image_url: str | None, quantity: int | None = None):
    global _products_cache, _products_cache_time
    
    # Update Supabase first (primary data store)
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
        
        res = sb.table("menu_items").update(payload).eq("id", int(item_id)).execute()
        
        # Update cache
        if _products_cache:
            for item in _products_cache:
                if item.get('id') == int(item_id):
                    item.update(payload)
                    break
        
        _products_cache_time = datetime.now().timestamp()
        _save_json_cache()
        
        return True
    except Exception as e:
        print(f"Error updating item in Supabase: {e}")
        raise e

def delete_item(item_id: int):
    global _products_cache, _products_cache_time
    
    # Delete from Supabase first (primary data store)
    try:
        sb = supabase()
        sb.table("menu_items").delete().eq("id", int(item_id)).execute()
        
        # Update cache
        if _products_cache:
            _products_cache = [p for p in _products_cache if p.get('id') != int(item_id)]
        
        _products_cache_time = datetime.now().timestamp()
        _save_json_cache()
        
        return True
    except Exception as e:
        print(f"Error deleting item from Supabase: {e}")
        raise e

# --- Inventory helpers ---

def set_item_quantity(item_id: int, quantity: int):
    """
    Set item quantity to a specific value.
    Updates Supabase directly.
    """
    global _products_cache, _products_cache_time
    
    try:
        sb = supabase()
        
        # Update Supabase
        update_res = sb.table("menu_items").update({"quantity": int(quantity)}).eq("id", int(item_id)).execute()
        
        if not update_res.data:
            print(f"Warning: Failed to set quantity in Supabase for item {item_id}")
            return False
        
        # Update cache
        if _products_cache:
            for item in _products_cache:
                if item.get('id') == int(item_id):
                    item['quantity'] = int(quantity)
                    break
        
        _products_cache_time = datetime.now().timestamp()
        _save_json_cache()
        
        if IS_PRODUCTION:
            print(f"✓ Set quantity for item {item_id} to {quantity}")
        
        return True
        
    except Exception as e:
        print(f"Error in set_item_quantity: {e}")
        return False

def change_item_quantity(item_id: int, delta: int):
    """
    Change item quantity by delta amount.
    Always gets current quantity from Supabase to ensure accuracy.
    """
    global _products_cache, _products_cache_time
    
    try:
        sb = supabase()
        
        # First, get the current quantity directly from Supabase
        res = sb.table("menu_items").select("quantity").eq("id", int(item_id)).limit(1).execute()
        
        if res.data and len(res.data) > 0:
            current_quantity = int(res.data[0].get("quantity", 0))
        else:
            print(f"Warning: Item {item_id} not found in Supabase")
            return False
        
        # Calculate new quantity
        new_quantity = max(0, current_quantity + int(delta))
        
        # Update Supabase with the new quantity
        update_res = sb.table("menu_items").update({"quantity": new_quantity}).eq("id", int(item_id)).execute()
        
        if not update_res.data:
            print(f"Warning: Failed to update quantity in Supabase for item {item_id}")
            return False
        
        # Update cache
        if _products_cache:
            for item in _products_cache:
                if item.get('id') == int(item_id):
                    item['quantity'] = new_quantity
                    break
        
        _products_cache_time = datetime.now().timestamp()
        _save_json_cache()
        
        print(f"✓ Updated quantity for item {item_id}: {current_quantity} → {new_quantity} (delta: {delta})")
        
        return True
        
    except Exception as e:
        print(f"Error in change_item_quantity: {e}")
        return False

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

# --- Cache initialization ---

def initialize_cache_from_supabase():
    """
    Initialize JSON cache from Supabase data (call this on app startup).
    """
    global _products_cache, _products_cache_time, _categories_cache, _categories_cache_time
    
    try:
        sb = supabase()
        
        # Load products from Supabase
        try:
            res = sb.table("menu_items").select("id,name,description,price,image_url,quantity,category_id,created_at").order("created_at", desc=True).execute()
            supabase_products = res.data or []
        except Exception:
            res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").order("created_at", desc=True).execute()
            supabase_products = res.data or []
        
        # Load categories from Supabase
        res = sb.table("menu_categories").select("id,name,created_at").order("name").execute()
        supabase_categories = res.data or []
        if not supabase_categories:
            # Ensure at least one category exists
            supabase_categories = [{"id": 1, "name": "All", "slug": "all"}]
        
        # Update cache
        _products_cache = supabase_products
        _products_cache_time = datetime.now().timestamp()
        _categories_cache = supabase_categories
        _categories_cache_time = datetime.now().timestamp()
        
        # Save to JSON files
        _save_json_cache()
        
        if IS_PRODUCTION:
            print(f"✓ Cache initialized from Supabase: {len(supabase_products)} products, {len(supabase_categories)} categories")
        return True
        
    except Exception as e:
        if IS_PRODUCTION:
            print(f"Error initializing cache from Supabase: {e}")
        return False

def refresh_cache_from_supabase():
    """
    Manually refresh the JSON cache from Supabase data.
    Useful for debugging or forcing a cache refresh.
    """
    global _products_cache, _products_cache_time, _categories_cache, _categories_cache_time
    
    try:
        sb = supabase()
        
        # Load products from Supabase
        try:
            res = sb.table("menu_items").select("id,name,description,price,image_url,quantity,category_id,created_at").order("created_at", desc=True).execute()
            supabase_products = res.data or []
        except Exception:
            res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").order("created_at", desc=True).execute()
            supabase_products = res.data or []
        
        # Load categories from Supabase
        res = sb.table("menu_categories").select("id,name,created_at").order("name").execute()
        supabase_categories = res.data or []
        
        if not supabase_categories:
            # Ensure at least one category exists
            supabase_categories = [{"id": 1, "name": "All", "slug": "all"}]
        
        # Update cache
        _products_cache = supabase_products
        _products_cache_time = datetime.now().timestamp()
        _categories_cache = supabase_categories
        _categories_cache_time = datetime.now().timestamp()
        
        # Save to JSON files
        _save_json_cache()
        
        if IS_PRODUCTION:
            print(f"✓ Cache refreshed from Supabase: {len(supabase_products)} products, {len(supabase_categories)} categories")
        return True
        
    except Exception as e:
        if IS_PRODUCTION:
            print(f"Error refreshing cache from Supabase: {e}")
        return False
