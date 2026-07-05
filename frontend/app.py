"""Aplicação do Frontend."""

import pybreaker
import requests

from tenacity import RetryError

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from client import get_orders, create_order  # pylint: disable=import-error

app = FastAPI(title="Frontend")

templates = Jinja2Templates(directory="templates")


@app.get("/")
def home(request: Request):
    """Renderiza a página inicial com a lista de pedidos."""
    service_unavailable = False

    try:
        orders = get_orders()

    except (
        pybreaker.CircuitBreakerError,
        requests.RequestException,
        RetryError,
    ):
        orders = []
        service_unavailable = True

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "orders": orders,
            "service_unavailable": service_unavailable,
        },
    )


@app.post("/create")
def create_order_route(description: str = Form(...)):
    """Processa o formulário de criação de pedido."""
    try:
        create_order(description)

    except (
        pybreaker.CircuitBreakerError,
        requests.RequestException,
        RetryError,
    ):
        pass

    return RedirectResponse(
        url="/",
        status_code=303,
    )
