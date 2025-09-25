# Restaurant Menu (Flask + Supabase)

A simple restaurant menu site that mirrors your `take-2-main` stack (Flask + Supabase + Render). Cooks can log into admin and add food categories (e.g., Breakfast, Lunch) and menu items (e.g., Curry, Fried Rice). This is a working design with basic forms and no custom JavaScript.

## Features
- Admin login (password-only) to add categories and menu items
- List categories and items on the public homepage
- Uses Supabase for data storage (same env style as your other app)
- Render-ready: `Procfile`, `render.yaml`, `requirements.txt`

## Environment Variables
Create a `.env` locally (or set env on Render) with:

- `SECRET_KEY` — Flask session secret (any random string)
- `ADMIN_PASSWORD` — password for admin login (default: `admin`)
- `SUPABASE_URL` — your Supabase project URL
- `SUPABASE_ANON_KEY` — anon key (or set `SUPABASE_SERVICE_ROLE_KEY` for server-side writes)
- `SUPABASE_SERVICE_ROLE_KEY` — preferred for server-side writes

Optionally:
- `SUPABASE_ASSETS_BUCKET` — defaults to `assets`

## Supabase Tables
Run these in Supabase SQL editor (or create via UI).

```sql
-- Categories table
create table if not exists menu_categories (
  id bigint primary key generated always as identity,
  name text not null unique,
  created_at timestamp with time zone default now()
);

-- Items table
create table if not exists menu_items (
  id bigint primary key generated always as identity,
  category_id bigint not null references menu_categories(id) on delete cascade,
  name text not null,
  description text,
  price numeric(10,2),
  created_at timestamp with time zone default now()
);

-- Optional site settings (key/value)
create table if not exists site_settings (
  key text primary key,
  value text
);
```

Storage (optional): create an `assets` bucket if you want to store images later.

## Local Development
1. Create a virtualenv and install requirements:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Create a `.env` file with the variables above.
3. Run:
   ```bash
   flask --app app run --debug
   ```
4. Open http://localhost:5000

## Admin
- Go to `/admin/login` to sign in.
- Admin dashboard at `/admin` lets you add categories and items.

## Deploy to Render
- Push to GitHub.
- Create a new Web Service in Render.
- Use `render.yaml` in this repo or set:
  - Start command: `gunicorn app:app`
  - Build command: `pip install -r requirements.txt`
- Add the environment variables from above.

## Notes
- This is intentionally minimal (no JS required). You can style further or add images later.
