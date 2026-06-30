from fastapi import FastAPI
from fastapi import Form
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import requests

app = FastAPI(title="Frontend")

templates = Jinja2Templates(directory="templates")

ORDER_SERVICE_URL = os.getenv(
    "ORDER_SERVICE_URL",
    "http://localhost:8001"
)


@app.get("/")
def home(request: Request):
    response = requests.get(
        f"{ORDER_SERVICE_URL}/orders",
        timeout=5
    )

    orders = response.json()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "orders": orders
        }
    )


@app.post("/create")
def create_order(description: str = Form(...)):
    requests.post(
        f"{ORDER_SERVICE_URL}/orders",
        json={
            "description": description
        },
        timeout=5
    )

    return RedirectResponse(
        url="/",
        status_code=303
    )