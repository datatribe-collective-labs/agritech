# Planting Intelligence website

A static site (no build step) that talks to the API. Screens: choose a city, crops for the city, companion crops for a crop (with the reason and the source), and an About page.

    frontend/
      index.html        page shell, top bar with the "you are here" trail
      config.js         the API address (the only setting)
      css/styles.css    layout, colours, animation (works from phone to wide laptop)
      js/format.js      safe templating and plain-language wording (unit tested)
      js/api.js         API calls
      js/views.js       the screens
      js/main.js        routing (links look like #/city/Lagos/plant/Zea%20mays)
      fonts/            Bricolage Grotesque and Figtree, SIL Open Font Licence

Every page has a link in the URL, so a farmer can share or bookmark any screen, and the browser's Back button works.

## Try it locally

    python -m http.server 8002 --directory frontend
    # open http://127.0.0.1:8002 (the API must allow this origin: API_CORS_ORIGINS=http://127.0.0.1:8002)

## Tests

    node --test frontend/tests/format.test.mjs

## Publish (on the server)

    git pull
    ./deploy/publish-frontend.sh
