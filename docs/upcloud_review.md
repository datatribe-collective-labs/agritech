# Trying UpCloud as Cloud Newcomers: What Worked and What Slowed Us Down

*A team review of onboarding, deployment and day-to-day reliability, written from the point of view of people building with AI.*

We recently moved a production data and machine learning stack onto UpCloud. This post covers two things: how the deployment went, and what we think UpCloud could do for a group of builders it isn’t reaching yet.

## Who we are in this story

A fast-growing group of people now build full-stack applications with AI tools, without a background in backend engineering or infrastructure security. They’re often called vibe coders, and we count ourselves among them. We know enough to see how much we don’t know.

For builders like us, AWS, MongoDB and Supabase didn’t fit the way we work. After adapting to one platform after another, some of us burned out and stopped trying. The platforms aren’t wrong. The steps between where we are and how cloud infrastructure works were missing. Three things got in the way:

- **Usage-based pricing.** We couldn’t forecast what a project would cost before it launched, which is stressful on a fixed budget.
- **Time limits on unused projects.** They make sense for the provider, but re-spinning an environment each time we came back broke our flow and slowed down quick iteration.
- **Unknown unknowns.** We worried about silent security misconfigurations and architecture mistakes we wouldn’t have the experience to spot. Knowing a little can freeze you more than knowing nothing.

## What we deployed

We run a managed PostgreSQL database and a single cloud server (2 CPUs, 8 GB RAM) in FI-HEL2. The server runs the whole stack as systemd services: Airflow, dbt, weekly machine learning retraining, and the API.

## What worked

- **Provisioning was quick** once we understood the configuration.
- **Managed PostgreSQL has been reliable.** It has stored our project data without trouble, and the server has had steady private network access to it.
- **One modest server carries a lot.** It handles Airflow, dbt, retraining and the API at the same time.
- **Our automated Sunday cycle runs cleanly.** It rebuilds the data, retrains the model, and deploys only if the new model beats the baseline. Each outcome is logged in a run table.

## Where we hesitated

**1. The private route to the database took a few minutes to appear.** The server and database were in the same zone, but the connection wasn’t ready right away, and nothing told us to expect that. We wondered whether we had misconfigured something. A short note in the documentation or interface, such as “Private routing may take a few minutes to initialize,” would save newcomers that worry.

**2. Python versions.** UpCloud’s Ubuntu LTS image uses Python 3.14, while Airflow 2.9.1 targets Python 3.8 to 3.11. The system’s default Python stayed as it was, and we installed an older interpreter separately for Airflow’s virtual environment. It was manageable, but a note about version compatibility would help anyone running data tooling.

**3. No web-based SQL tool.** We used psql from the terminal and it worked well. We wondered whether leaving a query tool out of the control panel is a deliberate choice or something still to explore. For people less comfortable in a terminal, a browser-based option could be a gentler first step.

## What we’d like to see

Our main feedback is about onboarding more than infrastructure. The infrastructure has done its job. What would help people like us:

- Short inline notes wherever a wait or a delay is normal.
- Clear guidance on tool and version compatibility.
- An onboarding path for AI-assisted builders, from a front-end they’ve built to a stable, secure backend, with plain explanations of what’s already handled for them and what isn’t.

People who arrive intimidated, or after a bad experience elsewhere, can become the most committed users if the first steps are clear.

## In short

UpCloud has been reliable for us. The gap is the way in. We’d be glad to talk with UpCloud about what we ran into and what would have helped.
