# Load test

Simulates farmers browsing the API at the same time. Run it from your own machine, not the server,
so the test measures what real users see (network included) and does not steal the server's CPU.

## Safety
- Start small and step up. Stop with Ctrl+C at any time.
- Test the API only. Do NOT point this at `/assistant/chat` on the live server: every question calls
  OpenAI and costs money. The assistant is tested separately, locally, with the offline model.

## Run (PowerShell)
    pip install locust
    cd loadtest
    # Step 1: 20 users, 2 minutes
    locust -f locustfile.py --host https://94-237-15-238.sslip.io --headless -u 20 -r 5 -t 2m --csv step1
    # Step 2: 100 users
    locust -f locustfile.py --host https://94-237-15-238.sslip.io --headless -u 100 -r 10 -t 3m --csv step2
    # Step 3: 500 users
    locust -f locustfile.py --host https://94-237-15-238.sslip.io --headless -u 500 -r 25 -t 3m --csv step3

## Read the result (the `*_stats.csv` files)
- 95th percentile under 1 second and failures under 1% means that step passed.
- When failures or 95th percentile jump, that step is the limit. Note the users count.
- On the server, watch while it runs: `top` (CPU) and `systemctl status planting-api`.
