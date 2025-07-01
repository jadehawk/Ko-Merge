FROM python:3.13.3-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5025
CMD ["gunicorn", "--bind", "0.0.0.0:5025", "app:app"]