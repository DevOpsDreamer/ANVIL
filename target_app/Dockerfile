FROM python:3.9-slim
WORKDIR /app
COPY server.py .
RUN pip install flask werkzeug
EXPOSE 5000
CMD ["python", "server.py"]
