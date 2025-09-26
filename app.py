import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv

from supabase_helpers import (
    list_categories,
    create_category,
    list_items,
    list_items_for_category,
    create_item,
    get_site_setting,
    set_site_setting,
    upload_logo_to_supabase,
    upload_item_image,
    get_item,
    update_category,
    delete_category,
    update_item,
    delete_item,
    change_item_quantity,
    initialize_cache_from_supabase,
    refresh_cache_from_supabase,
)

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev")

# Initialize cache from Supabase on startup
try:
    initialize_cache_from_supabase()
except Exception as e:
    print(f"Warning: Could not initialize cache from Supabase: {e}")
    print("App will use local JSON files as fallback")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# ---------- Helpers ----------

def is_logged_in():
    return session.get("admin") is True


def _site():
    return {
        "brand_name": get_site_setting("brand_name") or "Restaurant Menu",
        "logo_url": get_site_setting("logo_url") or "",
        "dark_mode": (get_site_setting("dark_mode") or "0") in ("1", "true", "True", "on"),
        "whatsapp_phone": (get_site_setting("whatsapp_phone") or "").strip(),
    }


def _cart():
    cart = session.get("cart") or {}
    # cart structure: { item_id: qty }
    return cart


def _save_cart(cart):
    session["cart"] = cart


# ---------- Public ----------

@app.route("/")
def index():
    site = _site()
    categories = list_categories()
    items_by_cat = {c["id"]: list_items_for_category(c["id"]) for c in categories}
    return render_template("index.html", site=site, categories=categories, items_by_cat=items_by_cat)


@app.route("/toggle-dark")
def toggle_dark():
    current = (get_site_setting("dark_mode") or "0") in ("1", "true", "True", "on")
    set_site_setting("dark_mode", "0" if current else "1")
    return redirect(request.referrer or url_for("index"))


# ---------- Admin Auth ----------

@app.route("/admin/login", methods=["GET", "POST"]) 
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Logged in", "success")
            return redirect(url_for("admin_home"))
        flash("Invalid password", "danger")
    return render_template("admin_login.html", title="Admin Login")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("index"))


# ---------- Admin Dashboard ----------

@app.route("/admin/debug/cache")
def admin_debug_cache():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    
    try:
        success = refresh_cache_from_supabase()
        if success:
            flash("Cache refreshed successfully from Supabase", "success")
        else:
            flash("Failed to refresh cache from Supabase", "danger")
    except Exception as e:
        flash(f"Error refreshing cache: {e}", "danger")
    
    return redirect(url_for("admin_items"))


@app.route("/admin/debug/quantity/<int:item_id>")
def admin_debug_quantity(item_id):
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    
    try:
        from supabase_helpers import supabase
        sb = supabase()
        res = sb.table("menu_items").select("id,name,quantity").eq("id", item_id).limit(1).execute()
        
        if res.data and len(res.data) > 0:
            item = res.data[0]
        else:
            flash(f"Item {item_id} not found in Supabase", "warning")
    except Exception as e:
        flash(f"Error checking Supabase quantity: {e}", "danger")
    
    return redirect(url_for("admin_home"))

# ---------- Admin Dashboard ---------

@app.route("/admin")
def admin_home():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    site = _site()
    return render_template("admin.html", site=site)


@app.route("/admin/settings", methods=["GET", "POST"]) 
def admin_settings():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        brand_name = request.form.get("brand_name", "").strip()
        dark_mode = request.form.get("dark_mode") == "on"
        whatsapp_phone = request.form.get("whatsapp_phone", "").strip()
        # Optional logo upload from settings page
        file = request.files.get("logo")
        if brand_name:
            set_site_setting("brand_name", brand_name)
            flash("Brand name updated", "success")
        else:
            flash("Brand name cannot be empty", "danger")
        set_site_setting("dark_mode", "1" if dark_mode else "0")
        if file and file.filename.strip():
            try:
                url = upload_logo_to_supabase(file)
                set_site_setting("logo_url", url)
                flash("Logo updated!", "success")
            except Exception as e:
                flash(f"Logo upload failed: {e}", "danger")
        # Basic WhatsApp E.164-like validation: allow + and digits 8-15
        if whatsapp_phone:
            import re
            if re.fullmatch(r"\+?[0-9]{8,15}", whatsapp_phone):
                set_site_setting("whatsapp_phone", whatsapp_phone)
                flash("WhatsApp number saved", "success")
            else:
                flash("Invalid WhatsApp number format. Use + and digits only.", "danger")
        return redirect(url_for("admin_settings"))
    # GET
    site = _site()
    return render_template("admin_settings.html", site=site)


# ---------- Template Context ----------

@app.context_processor
def inject_nav_counts():
    cart = _cart()
    count = sum(int(q) for q in cart.values())
    return {"cart_count": count}


# ---------- Admin: Edit/Delete ----------

@app.post("/admin/categories/update")
def admin_category_update():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    cid = request.form.get("id")
    name = request.form.get("name")
    try:
        update_category(cid, name)
        flash("Category updated", "success")
    except Exception as e:
        flash(f"Update failed: {e}", "danger")
    return redirect(url_for("admin_categories"))


@app.post("/admin/categories/delete")
def admin_category_delete():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    cid = request.form.get("id")
    try:
        delete_category(cid)
        flash("Category deleted", "info")
    except Exception as e:
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for("admin_categories"))


@app.post("/admin/items/update")
def admin_item_update():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    iid = request.form.get("id")
    name = request.form.get("name")
    description = request.form.get("description")
    price = request.form.get("price")
    image_url = request.form.get("image_url")
    quantity = request.form.get("quantity")
    try:
        update_item(iid, name, description, price, image_url, quantity)
        flash("Item updated", "success")
    except Exception as e:
        flash(f"Update failed: {e}", "danger")
    return redirect(url_for("admin_items"))


@app.route("/admin/items/edit/<int:item_id>", methods=["GET", "POST"])
def admin_item_edit(item_id):
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    item = get_item(item_id)
    if not item:
        flash("Item not found", "danger")
        return redirect(url_for("admin_items"))
    cats = list_categories()
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")
        quantity = request.form.get("quantity")
        image_url = request.form.get("image_url")
        file = request.files.get("image")
        if file and file.filename.strip():
            try:
                image_url = upload_item_image(file)
            except Exception as e:
                flash(f"Image upload failed: {e}", "warning")
        try:
            update_item(item_id, name, description, price, image_url, quantity)
            flash("Item updated", "success")
            return redirect(url_for("admin_items"))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")
    return render_template("admin_item_edit.html", item=item, categories=cats)


# ---------- Categories ----------

@app.route("/admin/categories", methods=["GET", "POST"]) 
def admin_categories():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        name = request.form.get("name")
        try:
            create_category(name)
            flash("Category saved", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("admin_categories"))
    cats = list_categories()
    return render_template("admin_categories.html", categories=cats)


# ---------- Items ----------

@app.route("/admin/items", methods=["GET", "POST"]) 
def admin_items():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    cats = list_categories()
    if request.method == "POST":
        category_id = request.form.get("category_id")
        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")
        quantity = request.form.get("quantity")
        image_url = None
        file = request.files.get("image")
        if file and file.filename.strip():
            try:
                image_url = upload_item_image(file)
            except Exception as e:
                flash(f"Image upload failed: {e}", "warning")
        try:
            create_item(category_id, name, description, price, image_url, quantity)
            flash("Item saved", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("admin_items"))
    items = list_items()
    return render_template("admin_items.html", categories=cats, items=items)


# ---------- Cart ----------

@app.route("/cart")
def cart_view():
    site = _site()
    cart = _cart()
    items = []
    subtotal = 0.0
    for item_id, qty in cart.items():
        itm = get_item(item_id)
        if not itm:
            continue
        line_total = (float(itm.get("price") or 0) * int(qty))
        subtotal += line_total
        items.append({"item": itm, "qty": int(qty), "line_total": line_total})
    return render_template("cart.html", site=site, items=items, subtotal=subtotal)


@app.route("/cart/add", methods=["POST"]) 
def cart_add():
    item_id = int(request.form.get("item_id"))
    req_qty = max(1, int(request.form.get("qty", 1)))
    itm = get_item(item_id)
    available = None
    try:
        available = int((itm or {}).get("quantity"))
    except Exception:
        available = None
    cart = _cart()
    current_in_cart = int(cart.get(str(item_id), 0))
    if available is not None:
        # Cap added quantity so total in cart does not exceed available
        can_add = max(0, available - current_in_cart)
        add_qty = min(req_qty, can_add)
    else:
        add_qty = req_qty
    if add_qty <= 0:
        flash("Not enough stock", "warning")
        return redirect(request.referrer or url_for("index"))
    cart[str(item_id)] = current_in_cart + add_qty
    _save_cart(cart)
    flash("Added to cart", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/remove", methods=["POST"]) 
def cart_remove():
    item_id = str(request.form.get("item_id"))
    cart = _cart()
    if item_id in cart:
        del cart[item_id]
        _save_cart(cart)
        flash("Removed item", "info")
    return redirect(url_for("cart_view"))

@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    cart = _cart()
    if not cart:
        flash("Your cart is empty", "warning")
        return redirect(url_for("cart"))

    customer_name = request.form.get("customer_name", "").strip()
    if not customer_name:
        flash("Please enter your name for the order", "danger")
        return redirect(url_for("cart"))

    site = _site()
    whatsapp_phone = site.get("whatsapp_phone") if site else None
    if not whatsapp_phone:
        flash("WhatsApp checkout is not configured", "warning")
        return redirect(url_for("cart"))

    lines = [f"🛒 Order from {customer_name}"]
    lines.append("=" * 30)
    subtotal = 0.0
    for item_id, qty in cart.items():
        itm = get_item(item_id)
        if not itm:
            continue
        price = float(itm.get("price") or 0)
        line_total = price * int(qty)
        subtotal += line_total
        lines.append(f"{itm['name']} x{qty} - ${line_total:.2f}")
        # Decrement inventory
        try:
            success = change_item_quantity(item_id, -int(qty))
            if not success:
                print(f"Warning: Failed to update inventory for item {item_id}")
                flash(f"Warning: Could not update inventory for {itm['name']}", "warning")
        except Exception as e:
            print(f"Error updating inventory for item {item_id}: {e}")
            flash(f"Error updating inventory for {itm['name']}", "danger")
    lines.append("=" * 30)
    lines.append(f"Subtotal: ${subtotal:.2f}")
    message = "\n".join(lines)

    # If WhatsApp configured, redirect to wa.me
    if whatsapp_phone:
        import urllib.parse
        url = f"https://wa.me/{whatsapp_phone.lstrip('+')}?text={urllib.parse.quote(message)}"
        # clear cart after creating URL
        session.pop("cart", None)
        return redirect(url)
    else:
        flash("WhatsApp checkout is not configured", "warning")
        return redirect(url_for("cart"))
