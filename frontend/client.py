import requests

from tenacity import retry, stop_after_attempt, wait_fixed

from config import ORDER_SERVICE_URL


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def get_orders():
    response = requests.get(
        f"{ORDER_SERVICE_URL}/orders",
        timeout=3
    )

    response.raise_for_status()

    return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def create_order(description: str):
    response = requests.post(
        f"{ORDER_SERVICE_URL}/orders",
        json={"description": description},
        timeout=3
    )

    response.raise_for_status()