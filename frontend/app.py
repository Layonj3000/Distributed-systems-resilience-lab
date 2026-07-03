from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from client import get_orders, create_order

app = FastAPI(title="Frontend")

templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    orders = get_orders()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "orders": orders
        }
    )


@app.post("/create")
def create_order_route(description: str = Form(...)):
    create_order(description)

    return RedirectResponse(
        url="/",
        status_code=303
    )