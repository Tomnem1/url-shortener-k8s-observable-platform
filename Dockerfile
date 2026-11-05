FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin nonroot
WORKDIR /containerized-url-shortener
COPY ./requirements.txt /containerized-url-shortener/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app /containerized-url-shortener/app
EXPOSE 8000
# 10001 = the "nonroot" user created above (numeric so Kubernetes runAsNonRoot can verify it)
USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
