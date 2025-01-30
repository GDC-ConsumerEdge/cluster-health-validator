FROM --platform=linux/amd64 python:3.12-alpine

ENV PYTHONUNBUFFERED=1

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

CMD [ "gunicorn", "-b", "0.0.0.0:8080", "app:app" ]