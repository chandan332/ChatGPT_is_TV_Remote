FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends adb && rm -rf /var/lib/apt/lists/* && useradd -m -u 10001 adapter
RUN mkdir -p /home/adapter/.android && chown -R adapter:adapter /home/adapter/.android
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
USER adapter
ENV TV_ENDPOINT=192.168.68.51:5555
CMD ["python", "server.py"]
