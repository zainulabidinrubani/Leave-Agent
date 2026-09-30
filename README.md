# Leave Desk — Frontend

A single static page (no build step) styled as a paper leave ledger with
ink-stamp accents. Talks to your FastAPI backend's `/chat` endpoint.

## 1. Point it at your backend

Open `index.html` and change this line near the top of the `<script>`:

```js
const DEFAULT_API_URL = "http://localhost:8000";
```

to your deployed API's URL, e.g.:

```js
const DEFAULT_API_URL = "https://your-api.onrender.com";
```

(You can also override it at runtime for testing without editing the file,
by opening the page with `?api=https://your-api.onrender.com` appended to
the URL.)

## 2. Deploy to Vercel

**Option A — Vercel CLI**
```bash
npm i -g vercel
cd frontend
vercel
```
Follow the prompts (no build command needed — it's a static site).

**Option B — Vercel dashboard**
1. Push this `frontend/` folder to a GitHub repo.
2. Go to vercel.com → **Add New Project** → import the repo.
3. Framework preset: **Other** (or leave as detected — no build step required).
4. Deploy.

## 3. Enable CORS on the backend

Your FastAPI server must allow requests from your Vercel domain. In
`main.py` it currently allows all origins (`allow_origins=["*"]`) for ease
of testing — once you know your Vercel URL, tighten it:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-project.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 4. Backend must be publicly reachable

`http://localhost:8000` only works on your own machine. Deploy the FastAPI
backend somewhere public (Render, Railway, Fly.io) or tunnel it with ngrok
for testing, and use that URL as `DEFAULT_API_URL` above.

## Notes

- Conversation memory (`session_id`) is stored in the browser's
  `localStorage`, so a visitor's conversation continues across page
  refreshes but is specific to that browser/device.
- "start new conversation" clears the stored session so the next message
  starts a fresh thread on the backend.
