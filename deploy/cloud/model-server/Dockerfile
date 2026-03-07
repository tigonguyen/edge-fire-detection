FROM python:3.11-slim
RUN pip install --no-cache-dir flask
WORKDIR /serve
COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
