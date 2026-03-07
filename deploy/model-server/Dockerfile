FROM python:3.11-slim
WORKDIR /serve
RUN pip install --no-cache-dir flask
COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
