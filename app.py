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
)

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev")

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
    site = _site()
    return render_template("admin_settings.html", site=site)


# ---------- Branding (Logo Upload) ----------

@app.route("/admin/branding", methods=["GET", "POST"]) 
def admin_branding():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    site = _site()
    if request.method == "POST":
        file = request.files.get("logo")
        if not file or not file.filename.strip():
            flash("Please choose an image file.", "danger")
            return redirect(url_for("admin_branding"))
        try:
            url = upload_logo_to_supabase(file)
            set_site_setting("logo_url", url)
            flash("Logo updated!", "success")
            site["logo_url"] = url
        except Exception as e:
            flash(f"Upload failed: {e}", "danger")
        return redirect(url_for("admin_branding"))
    return render_template("admin_branding.html", site=site, current_logo=site.get("logo_url"))


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
        image_url = None
        file = request.files.get("image")
        if file and file.filename.strip():
            try:
                image_url = upload_item_image(file)
            except Exception as e:
                flash(f"Image upload failed: {e}", "warning")
        try:
            create_item(category_id, name, description, price, image_url)
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
    qty = int(request.form.get("qty", 1))
    cart = _cart()
    cart[str(item_id)] = cart.get(str(item_id), 0) + max(1, qty)
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
    site = _site()
    whatsapp_phone = site.get("whatsapp_phone")
    customer_name = request.form.get("customer_name", "").strip() or "Guest"
    cart = _cart()
    if not cart:
        flash("Your cart is empty", "warning")
        return redirect(url_for("cart_view"))
    # Build message
    lines = []
    lines.append(f"Order for {customer_name}")
    lines.append("--------------------------------")
    subtotal = 0.0
    for item_id, qty in cart.items():
        itm = get_item(item_id)
        if not itm:
            continue
        price = float(itm.get("price") or 0)
        line_total = price * int(qty)
        subtotal += line_total
        lines.append(f"{itm['name']} x{qty} - ${line_total:.2f}")
    lines.append("--------------------------------")
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
        flash("WhatsApp is not configured. Set a phone number in Admin → Settings.", "danger")
        return redirect(url_for("admin_settings"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
