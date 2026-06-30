from fastapi import FastAPI

app = FastAPI(title="Order Service")

@app.get("/")
def root():
    return {
        "service": "order-service",
        "status": "running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }