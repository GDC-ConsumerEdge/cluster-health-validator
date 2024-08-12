FROM --platform=linux/amd64 python:3.12-alpine

WORKDIR /app

COPY app /app
RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8080

CMD [ "gunicorn", "-b", "0.0.0.0:8080", "app:app" ]
