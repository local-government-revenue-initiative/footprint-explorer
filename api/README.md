# Overture buildings API

## Deploy on Render (free)
1. Put this `api` folder in your GitHub repo (next to `index.html`).
2. render.com > New > Web Service > connect the repo.
3. Root Directory: `api`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Instance type: Free. Copy the URL (https://xxx.onrender.com).
7. Open `index.html` (Vercel), paste the URL in the "API address" field.

Check: open `https://xxx.onrender.com/buildings?minx=28.55&miny=-20.17&maxx=28.57&maxy=-20.15`
(a small box in Bulawayo) and you should see GeoJSON.

The free instance sleeps after inactivity: the first request takes about 30 s.
