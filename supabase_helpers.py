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

def _load_json_cache():
    """Load data from JSON cache with timestamp checking and Supabase sync"""
    global _products_cache, _products_cache_time, _categories_cache, _categories_cache_time
    current_time = datetime.now().timestamp()
    
    # Load products cache if expired or empty
    if _products_cache is None or (current_time - _products_cache_time) > CACHE_DURATION:
        products_loaded = False
        if os.path.exists(PRODUCTS_FILE):
            try:
                with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                    _products_cache = json.load(f)
                    _products_cache_time = current_time
                    products_loaded = True
                    if IS_PRODUCTION:
                        print(f"✓ Loaded {len(_products_cache)} products from cache")
            except Exception as e:
                print(f"Warning: Error loading products cache: {e}")
                _products_cache = []
        else:
            _products_cache = []
        
        # If no cache or cache loading failed, try to load from Supabase
        if not products_loaded or not _products_cache:
            try:
                sb = supabase()
                try:
                    res = sb.table("menu_items").select("id,name,description,price,image_url,quantity,category_id,created_at").order("created_at", desc=True).execute()
                    supabase_products = res.data or []
                except Exception:
                    res = sb.table("menu_items").select("id,name,description,price,category_id,created_at").order("created_at", desc=True).execute()
                    supabase_products = res.data or []
                
                if supabase_products:
                    _products_cache = supabase_products
                    _products_cache_time = current_time
                    _save_json_cache()  # Save to cache
                    if IS_PRODUCTION:
                        print(f"✓ Loaded {len(supabase_products)} products from Supabase")
                else:
                    # Create default products if none exist
                    _products_cache = []
            except Exception as e:
                print(f"Error loading products from Supabase: {e}")
                if not products_loaded:
                    _products_cache = []
    
    # Load categories cache if expired or empty
    if _categories_cache is None or (current_time - _categories_cache_time) > CACHE_DURATION:
        categories_loaded = False
        if os.path.exists(CATEGORIES_FILE):
            try:
                with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
                    _categories_cache = json.load(f)
                    _categories_cache_time = current_time
                    categories_loaded = True
                    if IS_PRODUCTION:
                        print(f"✓ Loaded {len(_categories_cache)} categories from cache")
            except Exception as e:
                print(f"Warning: Error loading categories cache: {e}")
                _categories_cache = [{"id": 1, "name": "All", "slug": "all"}]
        else:
            _categories_cache = [{"id": 1, "name": "All", "slug": "all"}]
        
        # If no cache or cache loading failed, try to load from Supabase
        if not categories_loaded or not _categories_cache:
            try:
                sb = supabase()
                res = sb.table("menu_categories").select("id,name,created_at").order("name").execute()
                supabase_categories = res.data or []
                
                if supabase_categories:
                    _categories_cache = supabase_categories
                    _categories_cache_time = current_time
                    _save_json_cache()  # Save to cache
                    if IS_PRODUCTION:
                        print(f"✓ Loaded {len(supabase_categories)} categories from Supabase")
                else:
                    # Ensure at least one category exists
                    _categories_cache = [{"id": 1, "name": "All", "slug": "all"}]
                    _save_json_cache()
            except Exception as e:
                print(f"Error loading categories from Supabase: {e}")
                if not categories_loaded:
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
    """Load categories from in-memory cache first, then fallback to Supabase."""
    global _categories_cache, _categories_cache_time
    # Try in-memory cache first
    if _categories_cache:
        return _categories_cache
    
    # Fallback to Supabase
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
        return [{"id": 1, "name": "All", "slug": "all"}]

def create_category(name: str):
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name is required")
    
    # Update in-memory cache directly (more reliable than loading from JSON)
    global _categories_cache
    if _categories_cache:
        new_id = max([c.get('id', 0) for c in _categories_cache] + [0]) + 1
        new_category = {"id": new_id, "name": name, "slug": name.lower().replace(' ', '-')}
        _categories_cache.append(new_category)
    else:
        new_id = 1
        new_category = {"id": new_id, "name": name, "slug": name.lower().replace(' ', '-')}
        _categories_cache = [new_category]
    
    # Save to cache
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
    
    return new_category

def update_category(category_id: int, name: str):
    # Update in-memory cache directly (more reliable than loading from JSON)
    if _categories_cache:
        for cat in _categories_cache:
            if cat.get('id') == category_id:
                cat['name'] = (name or "").strip()
                cat['slug'] = name.lower().replace(' ', '-')
                break
    
    # Save to cache
    _categories_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also update Supabase
    try:
        sb = supabase()
        sb.table("menu_categories").update({"name": (name or "").strip()}).eq("id", int(category_id)).execute()
    except Exception as e:
        print(f"Error updating category in Supabase: {e}")
    
    return True

def delete_category(category_id: int):
    # Update in-memory cache directly (more reliable than loading from JSON)
    if _categories_cache:
        _categories_cache = [c for c in _categories_cache if c.get('id') != category_id]
    
    # Save to cache
    _categories_cache_time = datetime.now().timestamp()
    _save_json_cache()
    
    # Also delete from Supabase
    try:
        sb = supabase()
        sb.table("menu_categories").delete().eq("id", int(category_id)).execute()
    except Exception as e:
        print(f"Error deleting category from Supabase: {e}")
    
    return True

# --- Items ---

def list_items():
    global _products_cache, _products_cache_time
    """Load items from in-memory cache first, then fallback to Supabase."""
    # Try in-memory cache first
    if _products_cache:
        return _products_cache
    
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
        _products_cache = data
        _products_cache_time = datetime.now().timestamp()
        
        return data
    except Exception as e:
        print(f"Error loading items from Supabase: {e}")
        return []


def list_items_for_category(category_id: int):
    """Load items for a specific category from in-memory cache first, then fallback to Supabase."""
    # Try in-memory cache first
    if _products_cache:
        return [item for item in _products_cache if item.get('category_id') == category_id]
    
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
        else:
            # Fallback: create item structure
            new_item = {
                "id": int(datetime.now().timestamp()),  # Temporary ID
                "category_id": int(category_id),
                "name": name,
                "description": (description or "").strip() or None,
                "price": float(price) if price not in (None, "") else None,
                "image_url": (image_url or "").strip() or None,
                "quantity": int(quantity) if quantity not in (None, "") else 0,
                "created_at": datetime.utcnow().isoformat()
            }
    except Exception as e:
        print(f"Error saving item to Supabase: {e}")
        # Fallback: create item without Supabase
        new_item = {
            "id": int(datetime.now().timestamp()),
            "category_id": int(category_id),
            "name": name,
            "description": (description or "").strip() or None,
            "price": float(price) if price not in (None, "") else None,
            "image_url": (image_url or "").strip() or None,
            "quantity": int(quantity) if quantity not in (None, "") else 0,
            "created_at": datetime.utcnow().isoformat()
        }
    
    # Update in-memory cache directly (more reliable than loading from JSON)
    if _products_cache:
        _products_cache.append(new_item)
    else:
        _products_cache = [new_item]
    
    # Also update JSON cache for persistence
    _save_json_cache()
    
    # Update timestamp
    _products_cache_time = datetime.now().timestamp()
    
    return new_item


def get_item(item_id: int):
    """Get a single item from in-memory cache first, then fallback to Supabase."""
    # Try in-memory cache first
    if _products_cache:
        for item in _products_cache:
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
        
        sb.table("menu_items").update(payload).eq("id", int(item_id)).execute()
    except Exception as e:
        print(f"Error updating item in Supabase: {e}")
    
    # Update in-memory cache directly (more reliable than loading from JSON)
    if _products_cache:
        for item in _products_cache:
            if item.get('id') == item_id:
                item['name'] = (name or "").strip()
                item['description'] = (description or "").strip() or None
                item['price'] = float(price) if price not in (None, "") else None
                item['image_url'] = (image_url or "").strip() or None
                if quantity is not None:
                    item['quantity'] = int(quantity) if quantity else 0
                break
    
    # Also update JSON cache for persistence
    _save_json_cache()
    
    # Update timestamp
    _products_cache_time = datetime.now().timestamp()
    
    return True


def delete_item(item_id: int):
    # Delete from Supabase first (primary data store)
    try:
        sb = supabase()
        sb.table("menu_items").delete().eq("id", int(item_id)).execute()
    except Exception as e:
        print(f"Error deleting item from Supabase: {e}")
    
    # Update in-memory cache directly (more reliable than loading from JSON)
    if _products_cache:
        _products_cache = [p for p in _products_cache if p.get('id') != item_id]
    
    # Also update JSON cache for persistence
    _save_json_cache()
    
    # Update timestamp
    _products_cache_time = datetime.now().timestamp()
    
    return True

# --- Inventory helpers ---

def set_item_quantity(item_id: int, quantity: int):
    """
    Set item quantity to a specific value.
    Updates both Supabase and JSON cache.
    """
    try:
        sb = supabase()
        
        # Update Supabase first (primary data store)
        try:
            update_res = sb.table("menu_items").update({"quantity": int(quantity)}).eq("id", int(item_id)).execute()
            if not update_res.data:
                print(f"Warning: Failed to set quantity in Supabase for item {item_id}")
                return False
        except Exception as e:
            print(f"Error updating quantity in Supabase: {e}")
            return False
        
        # Update in-memory cache directly (more reliable than loading from JSON)
        if _products_cache:
            for item in _products_cache:
                if item.get('id') == item_id:
                    item['quantity'] = int(quantity)
                    break
        
        # Also update JSON cache for persistence
        _save_json_cache()
        
        # Update timestamp
        _products_cache_time = datetime.now().timestamp()
        
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
    try:
        sb = supabase()
        
        # First, get the current quantity directly from Supabase
        try:
            res = sb.table("menu_items").select("quantity").eq("id", int(item_id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                current_quantity = int(res.data[0].get("quantity", 0))
            else:
                print(f"Warning: Item {item_id} not found in Supabase")
                return False
        except Exception as e:
            print(f"Error getting current quantity from Supabase: {e}")
            return False
        
        # Calculate new quantity
        new_quantity = max(0, current_quantity + int(delta))
        
        # Update Supabase with the new quantity
        try:
            update_res = sb.table("menu_items").update({"quantity": new_quantity}).eq("id", int(item_id)).execute()
            if not update_res.data:
                print(f"Warning: Failed to update quantity in Supabase for item {item_id}")
                return False
        except Exception as e:
            print(f"Error updating quantity in Supabase: {e}")
            return False
        
        # Update in-memory cache directly (more reliable than loading from JSON)
        if _products_cache:
            for item in _products_cache:
                if item.get('id') == item_id:
                    item['quantity'] = new_quantity
                    break
        
        # Also update JSON cache for persistence
        _save_json_cache()
        
        # Update timestamp
        _products_cache_time = datetime.now().timestamp()
        
        if IS_PRODUCTION:
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
    Same as refresh_cache_from_supabase but with different logging.
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
