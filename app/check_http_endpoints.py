
import logging
import time
import requests
import concurrent.futures
from pydantic import BaseModel, Field
from typing import List
from prometheus_client import Counter, Histogram

log = logging.getLogger('check.http_endpoints')

HTTP_ENDPOINT_SUCCESS_TOTAL = Counter(
    'http_endpoint_success_total',
    'Total number of successful HTTP endpoint checks',
    ['endpoint_name']
)
HTTP_ENDPOINT_FAILURE_TOTAL = Counter(
    'http_endpoint_failure_total',
    'Total number of failed HTTP endpoint checks',
    ['endpoint_name']
)
HTTP_ENDPOINT_LATENCY_SECONDS = Histogram(
    'http_endpoint_latency_seconds',
    'Latency of HTTP endpoint checks in seconds',
    ['endpoint_name']
)

class Endpoint(BaseModel):
    name: str
    url: str
    timeout: int = 10
    method: str = 'GET'

class HttpEndpointsParameters(BaseModel):
    endpoints: List[Endpoint] = Field(..., min_items=1)

class CheckHttpEndpoints:
    def __init__(self, parameters: dict):
        self.params = HttpEndpointsParameters(**parameters)

    def is_healthy(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.check_endpoint, endpoint): endpoint for endpoint in self.params.endpoints}
            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    return False
        log.info("Check http endpoints passed")
        return True

    def check_endpoint(self, endpoint: Endpoint):
        start_time = time.time()
        try:
            response = requests.request(endpoint.method, endpoint.url, timeout=endpoint.timeout)
            if not response.ok:
                log.error(f"HTTP endpoint {endpoint.name} ({endpoint.url}) returned status code {response.status_code}")
                HTTP_ENDPOINT_FAILURE_TOTAL.labels(endpoint_name=endpoint.name).inc()
                return False
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to HTTP endpoint {endpoint.name} ({endpoint.url}): {e}")
            HTTP_ENDPOINT_FAILURE_TOTAL.labels(endpoint_name=endpoint.name).inc()
            return False
        finally:
            latency = time.time() - start_time
            HTTP_ENDPOINT_LATENCY_SECONDS.labels(endpoint_name=endpoint.name).observe(latency)

        HTTP_ENDPOINT_SUCCESS_TOTAL.labels(endpoint_name=endpoint.name).inc()
        return True
