# Planting Intelligence website

Next.js (App Router, TypeScript). Screens: choose a city, crops for the city, companion crops for a crop (with the reason and the source), and an About page. Every screen has its own address, a "you are here" trail where each part is a link, and a back link; the browser's Back button works.

    app/                 pages (/, /city/[city], /city/[city]/plant/[species], /about), layout, fonts, styles
    components/          Trail, CityPicker, CropList, Parts (stat tiles, companion card, year chart), Sprouts
    lib/api.ts           server-side calls to the API (the browser never calls the API)
    lib/format.ts        plain-language wording for the API's codes (unit tested)

Pages are fetched on the server and kept for five minutes, so a new model run shows up on its own.

## Settings

| Variable | Meaning | Default |
|---|---|---|
| `API_URL` | where the API lives, as seen from the server running the website | `https://94-237-15-238.sslip.io` |

## "Let's discuss more" (AI chat)

A button on the city page and the crop page opens a chat panel. Farmers tap a suggested question or type their own; the assistant only explains the result on that page (see `assistant/README.md`). This is the one part where the browser talks to a server directly: it calls the assistant gateway, never the API.

    components/AskAssistant.tsx   the button and the panel (runs in the browser)
    lib/assistant.ts              calls to the gateway, the suggested questions, the friendly error messages

| Variable | Meaning | Default |
|---|---|---|
| `NEXT_PUBLIC_ASSISTANT_URL` | where the assistant gateway is, as seen from the farmer's browser (set before `npm run build`) | `https://94-237-15-238.sslip.io/assistant` |

## Run it on your laptop

    cd frontend
    npm install
    API_URL=https://94-237-15-238.sslip.io npm run dev      # open http://localhost:3000

## Tests

    npm test          # wording and fit-check logic
    npm run lint      # TypeScript check

## Deploy on the server

First time only (Node 20.9 or newer is required; `node -v`):

    apt install -y nodejs npm            # only if node is missing
    cp deploy/planting-web.service /etc/systemd/system/
    cp deploy/Caddyfile.example /etc/caddy/Caddyfile && systemctl reload caddy
    systemctl daemon-reload && systemctl enable planting-web

Every update:

    git pull
    ./deploy/deploy-web.sh

Fonts (Bricolage Grotesque, Figtree) are included under the SIL Open Font Licence, so the site loads nothing from other servers.
