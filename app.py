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
)

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# ---------- Helpers ----------

def is_logged_in():
    return session.get("admin") is True


# ---------- Public ----------

@app.route("/")
def index():
    site = {
        "brand_name": get_site_setting("brand_name") or "Restaurant Menu",
        "logo_url": get_site_setting("logo_url") or "",
        "dark_mode": (get_site_setting("dark_mode") or "0") in ("1", "true", "True", "on"),
    }
    categories = list_categories()
    items_by_cat = {c["id"]: list_items_for_category(c["id"]) for c in categories}
    return render_template("index.html", site=site, categories=categories, items_by_cat=items_by_cat)


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
    site = {
        "brand_name": get_site_setting("brand_name") or "Restaurant Menu",
        "logo_url": get_site_setting("logo_url") or "",
        "dark_mode": (get_site_setting("dark_mode") or "0") in ("1", "true", "True", "on"),
    }
    return render_template("admin.html", site=site)


@app.route("/admin/settings", methods=["GET", "POST"]) 
def admin_settings():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        brand_name = request.form.get("brand_name", "").strip()
        dark_mode = request.form.get("dark_mode") == "on"
        if brand_name:
            set_site_setting("brand_name", brand_name)
            flash("Brand name updated", "success")
        else:
            flash("Brand name cannot be empty", "danger")
        set_site_setting("dark_mode", "1" if dark_mode else "0")
        return redirect(url_for("admin_settings"))
    site = {
        "brand_name": get_site_setting("brand_name") or "Restaurant Menu",
        "dark_mode": (get_site_setting("dark_mode") or "0") in ("1", "true", "True", "on"),
    }
    return render_template("admin_settings.html", site=site)


# ---------- Branding (Logo Upload) ----------

@app.route("/admin/branding", methods=["GET", "POST"]) 
def admin_branding():
    if not is_logged_in():
        return redirect(url_for("admin_login"))
    site = {
        "brand_name": get_site_setting("brand_name") or "Restaurant Menu",
        "logo_url": get_site_setting("logo_url") or "",
        "dark_mode": (get_site_setting("dark_mode") or "0") in ("1", "true", "True", "on"),
    }
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
        try:
            create_item(category_id, name, description, price)
            flash("Item saved", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("admin_items"))
    items = list_items()
    return render_template("admin_items.html", categories=cats, items=items)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
