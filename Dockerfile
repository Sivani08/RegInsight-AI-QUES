FROM node:24-bookworm-slim AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements-app.txt requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY . .
COPY --from=frontend /ui/dist ./frontend/dist
EXPOSE 8000
CMD ["python","-m","uvicorn","backend.api.main:app","--host","0.0.0.0","--port","8000"]
