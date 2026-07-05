"""Cliente HTTP para o Order Service com circuit breaker e retry."""

import requests
import pybreaker
from tenacity import retry, stop_after_attempt, wait_fixed

from config import ORDER_SERVICE_URL  # pylint: disable=import-error

breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30)


@breaker
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def get_orders():
    """Retorna todos os pedidos do Order Service."""
    response = requests.get(f"{ORDER_SERVICE_URL}/orders", timeout=3)
    response.raise_for_status()
    return response.json()


@breaker
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def create_order(description: str):
    """Cria um novo pedido no Order Service."""
    response = requests.post(
        f"{ORDER_SERVICE_URL}/orders", json={"description": description}, timeout=3
    )

    response.raise_for_status()
