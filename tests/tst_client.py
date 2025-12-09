import time
import pytest

from mock import patch, Mock

from marketorestpython.client import MarketoClient
from marketorestpython.helper.exceptions import MarketoException


@pytest.fixture
def client():
    return MarketoClient('123-FDY-456', 'randomclientid', 'supersecret')


def test_marketo_client(client):
    assert client.host == 'https://123-FDY-456.mktorest.com'
    assert client.client_id == 'randomclientid'
    assert client.client_secret == 'supersecret'
    assert client.API_CALLS_MADE == 0
    assert client.API_LIMIT is None
    assert client.requests_timeout is None

    client = MarketoClient('123-FDY-456', 'randomclientid', 'supersecret', 20, requests_timeout=1.0)
    assert client.API_LIMIT == 20
    assert client.requests_timeout == 1.0

    client = MarketoClient('123-FDY-456', 'randomclientid', 'supersecret', requests_timeout=(1,2.0))
    assert client.requests_timeout == (1,2.0)

    invalid_requests_timeouts = ["a string", -1, (1,2,3), (1, -1), (1,"a string"), (1,)]
    for invalid_requests_timeout in invalid_requests_timeouts:
        with pytest.raises(AssertionError):
            MarketoClient('123-FDY-456', 'randomclientid', 'supersecret', 20, requests_timeout=invalid_requests_timeout)


@patch('marketorestpython.client.HttpLib')
def test_api_call(m_http_lib, client):
    get_request_mock = Mock(return_value={
        'access_token': '1234', 'expires_in': 1000, 'scope': '1'
    })
    request_mock = Mock(get=get_request_mock)
    m_http_lib.return_value = request_mock
    args = (1, 2, 3)
    kwargs = {'a': 1, 'b': 2}
    client._api_call('get', '/test', *args, **kwargs)
    get_request_mock.assert_called_with(*(('/test',) + args), **kwargs)
    assert client.API_CALLS_MADE == 1

    limit = 4
    client = MarketoClient('123-FDY-456', 'randomclientid', 'supersecret', limit)
    with pytest.raises(Exception) as excinfo:
        for i in xrange(limit):
            client._api_call('get', '/test', *args, **kwargs)
        assert excinfo.value == {
            'message': 'API Calls exceeded the limit : %s' % limit,
            'code': '416'
        }


@patch('marketorestpython.client.MarketoClient._api_call')
def test_authenticate(m_client_api_call, client):
    m_client_api_call.return_value = None
    with pytest.raises(Exception):
        client.authenticate()

    access_token = "cdf01657-110d-4155-99a7-f986b2ff13a0:int"
    token_type = "bearer"
    expires_in = 3599
    scope = "apis@acmeinc.com"
    m_client_api_call.return_value = {
        "access_token": access_token,
        "token_type": token_type,
        "expires_in": expires_in,
        "scope": scope
    }

    client.authenticate()
    m_client_api_call.assert_called_with(
        'get',
        client.host + '/identity/oauth/token',
        {
            'grant_type': 'client_credentials',
            'client_id': client.client_id,
            'client_secret': client.client_secret,
        }
    )

    assert client.token == access_token
    assert client.token_type == token_type
    assert client.expires_in == expires_in
    assert client.valid_until > time.time()
    assert client.scope == scope

    # credentials should still be valid
    client.authenticate()
    assert m_client_api_call.call_count == 2

    # test error handling
    client = MarketoClient('123-FDY-456', 'randomclientid', 'supersecret')
    m_client_api_call.return_value = {
        'error': 'invalid_client',
        'error_description': 'invalid secret'
    }
    with pytest.raises(Exception) as excinfo:
        client.authenticate()
        assert excinfo.value == 'invalid secret'


@patch('marketorestpython.client.MarketoClient.authenticate')
@patch('marketorestpython.client.MarketoClient._api_call')
def test_endpoint_responses(m_client_api_call, m_client_authenticate, client):
    m_client_authenticate.return_value = True

    m_client_api_call.return_value = None
    with pytest.raises(Exception) as excinfo:
        client.get_program_by_id(2600)
        assert excinfo == "Empty Response"

    m_client_api_call.return_value = {
        "success": False,
        "errors": [
            {
                "message": "Something went wrong.",
                "code": 1
            }
        ]
    }
    with pytest.raises(MarketoException) as excinfo:
        client.get_program_by_id(2600)
        assert excinfo == "Marketo API Error Code {}: {}".format(
            1,
            "Something went wrong."
        )

    m_client_api_call.return_value = {
        "success": True,
        "errors": []
    }
    assert client.get_program_by_id(2600) == []

    program_info = {
        "id": 2600,
        "name": "Foo"
    }
    m_client_api_call.return_value = {
        "success": True,
        "errors": [],
        "result": [program_info]
    }
    assert client.get_program_by_id(2600) == [program_info]
