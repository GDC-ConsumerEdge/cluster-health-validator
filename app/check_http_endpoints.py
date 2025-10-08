
import logging
import time
import requests
import concurrent.futures
from pydantic import BaseModel, Field
from typing import List
from prometheus_client import Counter, Histogram
import socket
from urllib.parse import urlparse

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
    ['endpoint_name', 'status']
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
        # Pre-resolve DNS to warm up the cache for timing purposes.
        try:
            parsed_url = urlparse(endpoint.url)
            hostname = parsed_url.hostname
            port = parsed_url.port or {'http': 80, 'https': 443}.get(parsed_url.scheme, 80)
            if hostname:
                socket.getaddrinfo(hostname, port)
        except (socket.gaierror, TypeError) as e:
            # Log the pre-resolution failure, but proceed. The actual request will handle the error.
            log.warning(f"DNS pre-resolution failed for {hostname}: {e}")

        start_time = time.time()
        try:
            response = requests.request(endpoint.method, endpoint.url, timeout=endpoint.timeout)
            if not response.ok:
                log.error(f"HTTP endpoint {endpoint.name} ({endpoint.url}) returned status code {response.status_code}")
                HTTP_ENDPOINT_FAILURE_TOTAL.labels(endpoint_name=endpoint.name).inc()
                HTTP_ENDPOINT_LATENCY_SECONDS.labels(endpoint_name=endpoint.name, status='failure').observe(response.elapsed.total_seconds())
                return False
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to HTTP endpoint {endpoint.name} ({endpoint.url}): {e}")
            HTTP_ENDPOINT_FAILURE_TOTAL.labels(endpoint_name=endpoint.name).inc()
            HTTP_ENDPOINT_LATENCY_SECONDS.labels(endpoint_name=endpoint.name, status='failure').observe(time.time() - start_time)
            return False

        HTTP_ENDPOINT_SUCCESS_TOTAL.labels(endpoint_name=endpoint.name).inc()
        HTTP_ENDPOINT_LATENCY_SECONDS.labels(endpoint_name=endpoint.name, status='success').observe(response.elapsed.total_seconds())
        return True
