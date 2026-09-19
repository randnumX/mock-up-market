FROM python:3.12-slim

WORKDIR /app

# System deps for pandas/numpy wheels build occasionally needed on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# --workers 1 is deliberate, not a placeholder: the live-trading scheduler
# (app/live/engine.py) is an in-process singleton (APScheduler + module-level
# state). Every gunicorn worker runs its own copy of the app, so more than
# one worker means every live session gets ticked once per worker - silently
# multiplying trades. Scale this service horizontally behind a load balancer
# instead of via --workers if you need more throughput; --threads gives
# concurrency for request handling without touching the scheduler count.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:5000", "--timeout", "120", "run:app"]
