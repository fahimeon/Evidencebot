FROM python:3.12-slim

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT expands; binds to 0.0.0.0 per the hackathon's runtime profile.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
