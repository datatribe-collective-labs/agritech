# Email alerts

Once a minute a small script checks the API, the assistant, server errors and the assistant's token budget, and emails you only when something is wrong.

| Alert | When it fires |
| --- | --- |
| API is not answering | `/health` fails 2 checks in a row |
| Assistant is down or off | its health fails 2 checks in a row, or it is switched off (kill switch or budget) |
| API is returning errors | 5 or more status-500 replies in 10 minutes |
| Token budget running low / used up | 80% / 100% of today's budget (once per day each) |

The same alert is not repeated within an hour. When a problem clears you get one "Recovered" email.

## Set up (once)

1. Create a Resend account with your Gmail and make an API key (sending access).
2. On the server, create the settings file. Replace the two values, do not paste the key anywhere else:

       nano /root/alerts.env

   Contents:

       RESEND_API_KEY=your_key_here
       ALERT_TO=your.address@gmail.com   (several: a@x.com,b@y.com)

3. Turn it on: `bash monitoring/alerts/install.sh`
4. Test: `set -a; . /root/alerts.env; set +a; python3 monitoring/alerts/alert_check.py --test`

## Tuning

Optional lines in `/root/alerts.env`: `ALERT_ERROR_LIMIT`, `ALERT_ERROR_WINDOW`, `ALERT_TOKEN_WARN_SHARE`, `ALERT_COOLDOWN_SECONDS`, `ALERT_FAILS_BEFORE`.
