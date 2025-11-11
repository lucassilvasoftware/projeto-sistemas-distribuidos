FROM python:3.10-slim
WORKDIR /app
COPY . /app
RUN pip install pyzmq
CMD ["python", "server.py"]
