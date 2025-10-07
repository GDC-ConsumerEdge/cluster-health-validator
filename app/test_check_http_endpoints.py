
import unittest
from unittest.mock import patch, MagicMock
from check_http_endpoints import (
    CheckHttpEndpoints,
    Endpoint,
)
import requests

class TestCheckHttpEndpoints(unittest.TestCase):
    @patch('check_http_endpoints.requests.request')
    @patch('check_http_endpoints.HTTP_ENDPOINT_LATENCY_SECONDS')
    @patch('check_http_endpoints.HTTP_ENDPOINT_FAILURE_TOTAL')
    @patch('check_http_endpoints.HTTP_ENDPOINT_SUCCESS_TOTAL')
    def test_check_endpoint_success(self, mock_success, mock_failure, mock_latency, mock_request):
        """Test check_endpoint returns True and increments success metrics."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_request.return_value = mock_response

        params = {"endpoints": [{"name": "example", "url": "http://example.com"}]}
        checker = CheckHttpEndpoints(parameters=params)
        endpoint = Endpoint(name="example", url="http://example.com")

        self.assertTrue(checker.check_endpoint(endpoint))
        mock_success.labels.assert_called_once_with(endpoint_name='example')
        mock_success.labels.return_value.inc.assert_called_once()
        mock_failure.labels.assert_not_called()
        mock_latency.labels.assert_called_once_with(endpoint_name='example')
        mock_latency.labels.return_value.observe.assert_called_once()

    @patch('check_http_endpoints.requests.request')
    @patch('check_http_endpoints.HTTP_ENDPOINT_LATENCY_SECONDS')
    @patch('check_http_endpoints.HTTP_ENDPOINT_FAILURE_TOTAL')
    @patch('check_http_endpoints.HTTP_ENDPOINT_SUCCESS_TOTAL')
    def test_check_endpoint_http_error(self, mock_success, mock_failure, mock_latency, mock_request):
        """Test check_endpoint returns False and increments failure metrics on HTTP error."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_request.return_value = mock_response

        params = {"endpoints": [{"name": "example", "url": "http://example.com"}]}
        checker = CheckHttpEndpoints(parameters=params)
        endpoint = Endpoint(name="example", url="http://example.com")

        self.assertFalse(checker.check_endpoint(endpoint))
        mock_failure.labels.assert_called_once_with(endpoint_name='example')
        mock_failure.labels.return_value.inc.assert_called_once()
        mock_success.labels.assert_not_called()
        mock_latency.labels.assert_called_once_with(endpoint_name='example')
        mock_latency.labels.return_value.observe.assert_called_once()

    @patch('check_http_endpoints.requests.request')
    @patch('check_http_endpoints.HTTP_ENDPOINT_LATENCY_SECONDS')
    @patch('check_http_endpoints.HTTP_ENDPOINT_FAILURE_TOTAL')
    @patch('check_http_endpoints.HTTP_ENDPOINT_SUCCESS_TOTAL')
    def test_check_endpoint_request_exception(self, mock_success, mock_failure, mock_latency, mock_request):
        """Test check_endpoint returns False and increments failure metrics on request exception."""
        mock_request.side_effect = requests.exceptions.RequestException("Connection error")

        params = {"endpoints": [{"name": "example", "url": "http://example.com"}]}
        checker = CheckHttpEndpoints(parameters=params)
        endpoint = Endpoint(name="example", url="http://example.com")

        self.assertFalse(checker.check_endpoint(endpoint))
        mock_failure.labels.assert_called_once_with(endpoint_name='example')
        mock_failure.labels.return_value.inc.assert_called_once()
        mock_success.labels.assert_not_called()
        mock_latency.labels.assert_called_once_with(endpoint_name='example')
        mock_latency.labels.return_value.observe.assert_called_once()

    @patch('check_http_endpoints.time.time')
    @patch('check_http_endpoints.requests.request')
    @patch('check_http_endpoints.HTTP_ENDPOINT_LATENCY_SECONDS')
    @patch('check_http_endpoints.HTTP_ENDPOINT_FAILURE_TOTAL')
    @patch('check_http_endpoints.HTTP_ENDPOINT_SUCCESS_TOTAL')
    def test_latency_metric(self, mock_success, mock_failure, mock_latency, mock_request, mock_time):
        """Test that latency is recorded for endpoint checks."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_request.return_value = mock_response
        mock_time.side_effect = [100, 100.5]

        params = {"endpoints": [{"name": "example", "url": "http://example.com"}]}
        checker = CheckHttpEndpoints(parameters=params)
        endpoint = Endpoint(name="example", url="http://example.com")

        checker.check_endpoint(endpoint)
        mock_latency.labels.assert_called_once_with(endpoint_name='example')
        mock_latency.labels.return_value.observe.assert_called_once_with(0.5)

    def test_init_invalid_parameters(self):
        """Test that initializing with invalid parameters raises a validation error."""
        with self.assertRaises(Exception):
            CheckHttpEndpoints(parameters={"endpoints": []})  # Empty list
        with self.assertRaises(Exception):
            CheckHttpEndpoints(parameters={})  # Missing endpoints
        with self.assertRaises(Exception):
            CheckHttpEndpoints(parameters={"endpoints": "not-a-list"})  # wrong type

if __name__ == '__main__':
    unittest.main()
