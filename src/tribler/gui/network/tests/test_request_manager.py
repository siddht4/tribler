import pytest

from tribler.gui.network.request_manager import RequestManager


# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture
def request_manager():
    return RequestManager()


def test_get_base_string(request_manager: RequestManager):
    assert request_manager.get_base_url() == 'http://localhost:20100/'


def test_get_message_from_error_string(request_manager: RequestManager):
    message = request_manager.get_message_from_error(
        {
            'error': 'message'
        }
    )
    assert message == 'message'


def test_get_message_from_error_dict_string(request_manager: RequestManager):
    message = request_manager.get_message_from_error(
        {
            'error': {
                'message': 'error message'
            }
        }
    )
    assert message == 'error message'


def test_get_message_from_error_any_dict(request_manager: RequestManager):
    message = request_manager.get_message_from_error(
        {
            'key': 'value'
        }
    )
    assert message == '{"key": "value"}'
