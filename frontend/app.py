from fastapi import FastAPI

app = FastAPI(title="Frontend")

@app.get("/")
def root():
    return {
        "service": "frontend",
        "status": "running"
    }