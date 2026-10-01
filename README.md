# LawPlanet 🏛️⚖️

A full-stack demo platform connecting clients with lawyers across India.
**Backend:** Python (Flask + SQLite). **Frontend:** vanilla HTML, CSS, and JavaScript.

## Quick Start

```bash
cd lawplanet
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser. The Flask server serves
both the REST API and the frontend, so there is nothing else to configure —
no separate frontend server, no CORS setup, no build step.

The SQLite database (`lawplanet.db`) is created automatically the first time
you run the app.

## Project Structure

```
lawplanet/
├── app.py                  # Flask backend: routes, auth, SQLite schema
├── requirements.txt
├── lawplanet.db             # created automatically on first run
├── pages/                   # all HTML pages
│   ├── index.html            # landing page + login/signup modal
│   ├── dashboard-client.html
│   ├── dashboard-lawyer.html
│   ├── find-lawyers.html     # client: search/browse lawyers
│   ├── lawyer-profile.html   # client: view a lawyer's public profile
│   ├── my-cases.html         # lawyer: manage case portfolio
│   ├── lawyer-profile-edit.html  # lawyer: edit professional details
│   ├── my-profile.html       # both roles: edit basic account info
│   ├── chats.html            # conversation list
│   └── chat-room.html        # two-pane chat UI (polls every 3s)
└── static/
    ├── css/style.css        # navy/gold/teal theme, fully responsive
    └── js/
        ├── api.js            # fetch wrapper + auth/session helpers
        └── layout.js         # shared sidebar renderer
```

## How Authentication Works

- Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 iterations) using only
  Python's standard library — no plaintext storage.
- On login/signup the server issues a random session token stored in a
  `sessions` table; the frontend keeps it in `localStorage` and sends it as
  `Authorization: Bearer <token>` on every API call.
- Row-level access is enforced in the Flask routes themselves (e.g. a lawyer
  can only edit their own cases; a user can only read conversations they are
  part of).

## Database Schema

| Table            | Purpose                                              |
|-------------------|-------------------------------------------------------|
| `users`           | Both clients and lawyers (role column distinguishes) |
| `lawyer_details`  | Bar Council ID, practice area, fees, bio, etc.       |
| `cases`           | A lawyer's case portfolio                            |
| `conversations`   | 1-to-1 client ↔ lawyer chat threads                  |
| `messages`        | Individual chat messages                             |
| `sessions`        | Active login tokens                                  |

## Chat / Real-Time Messaging

This demo uses lightweight polling (every 3 seconds) rather than WebSockets,
so it works with zero extra dependencies and no special server config. It's
easy to swap in Flask-SocketIO later if you want true push-based delivery.

## Sample Data

Use the signup form to create your own test accounts — no seed data is
included. Suggested test values, per the original spec:

- **Bar Council ID format:** `D/1234/2020` (Delhi), `M/5678/2018` (Maharashtra), `K/9012/2019` (Karnataka)
- **Cities:** Delhi, Mumbai, Bengaluru, Kolkata, Chennai, Hyderabad, Pune, Ahmedabad, Jaipur, Lucknow, Chandigarh
- **Practice Areas:** Civil, Criminal, Family, Property, Corporate, Tax, Labour, Constitutional, IPR, Consumer

## Security Notes

⚠️ This is a demo/learning project, not production-hardened:
- The Flask dev server (`app.run(debug=True)`) should never be used in production — use gunicorn/uWSGI behind a reverse proxy instead.
- Add HTTPS, CSRF protection, rate limiting, and stronger session expiry for real deployments.
- Bar Council IDs are stored as free text and are **not** verified against any real registry.
