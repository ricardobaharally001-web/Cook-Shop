# Add these routes to your existing app.py file (don't replace the whole file, just add these):

# Add this import at the top if not already there
from flask import jsonify

# Add this new route for checking cart status (add after the existing cart routes)
@app.route("/cart/status")
def cart_status():
    """API endpoint to check if cart is empty"""
    cart = _cart()
    return jsonify({"isEmpty": len(cart) == 0, "itemCount": len(cart)})

# Replace your existing cart_checkout route with this improved version:
@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    cart = _cart()
    if not cart:
        flash("Your cart is empty", "warning")
        return redirect(url_for("cart_view"))

    customer_name = request.form.get("customer_name", "").strip()
    if not customer_name:
        flash("Please enter your name for the order", "danger")
        return redirect(url_for("cart_view"))

    site = _site()
    whatsapp_phone = site.get("whatsapp_phone") if site else None
    if not whatsapp_phone:
        flash("WhatsApp checkout is not configured", "warning")
        return redirect(url_for("cart_view"))

    lines = [f"🛒 Order from {customer_name}"]
    lines.append("=" * 30)
    subtotal = 0.0
    
    # Track successful inventory updates
    inventory_errors = []
    
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
                inventory_errors.append(itm['name'])
                print(f"Warning: Failed to update inventory for item {item_id}")
        except Exception as e:
            inventory_errors.append(itm['name'])
            print(f"Error updating inventory for item {item_id}: {e}")
    
    lines.append("=" * 30)
    lines.append(f"Subtotal: ${subtotal:.2f}")
    
    # Add order timestamp
    from datetime import datetime
    lines.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    message = "\n".join(lines)

    # Clear cart first (before redirect)
    session.pop("cart", None)
    session.modified = True
    
    # Show any inventory warnings
    if inventory_errors:
        flash(f"Note: Inventory update pending for: {', '.join(inventory_errors)}", "info")
    
    # Redirect to WhatsApp
    if whatsapp_phone:
        import urllib.parse
        # Remove any + from the phone number for the URL
        clean_phone = whatsapp_phone.lstrip('+')
        url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
        
        # Add a success flash message that will show when they return
        session['checkout_success'] = True
        
        return redirect(url)
    else:
        flash("WhatsApp checkout is not configured", "warning")
        return redirect(url_for("cart_view"))

# Update the cart_view route to handle the success message:
@app.route("/cart")
def cart_view():
    site = _site()
    cart = _cart()
    
    # Check if we just completed a checkout
    checkout_success = session.pop('checkout_success', False)
    
    items = []
    subtotal = 0.0
    for item_id, qty in cart.items():
        itm = get_item(item_id)
        if not itm:
            continue
        line_total = (float(itm.get("price") or 0) * int(qty))
        subtotal += line_total
        items.append({"item": itm, "qty": int(qty), "line_total": line_total})
    
    # If checkout was successful and cart is empty, add success parameter
    if checkout_success and not cart:
        return redirect(url_for("cart_view") + "?checkout=success")
    
    return render_template("cart.html", site=site, items=items, subtotal=subtotal)
