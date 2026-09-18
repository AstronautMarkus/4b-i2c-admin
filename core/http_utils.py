import requests

from core.config import HTTP_TIMEOUT


def get_json(url, params=None, timeout=HTTP_TIMEOUT):
    """GET que devuelve el JSON decodificado, o None ante cualquier fallo de red/formato."""
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None
