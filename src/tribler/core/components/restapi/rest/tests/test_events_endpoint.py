import json
from asyncio import CancelledError, Event, create_task
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession

from tribler.core import notifications
from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.components.restapi.rest.events_endpoint import EventsEndpoint
from tribler.core.components.restapi.rest.rest_endpoint import RESTStreamResponse
from tribler.core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler.core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.notifier import Notifier
from tribler.core.version import version_id

messages_to_wait_for = set()


# pylint: disable=redefined-outer-name

@pytest.fixture(name='api_port')
def fixture_api_port(free_port):
    return free_port


@pytest.fixture(name='notifier')
def fixture_notifier(event_loop):
    return Notifier(loop=event_loop)


@pytest.fixture
async def endpoint(notifier):
    events_endpoint = EventsEndpoint(notifier)
    yield events_endpoint

    await events_endpoint.shutdown()


@pytest.fixture(name='reported_error')
def fixture_reported_error():
    return ReportedError('type', 'text', {})


@pytest.fixture(name="rest_manager")
async def fixture_rest_manager(api_port, tmp_path, endpoint):
    config = TriblerConfig()
    config.api.http_enabled = True
    config.api.http_port = api_port
    root_endpoint = RootEndpoint(middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])
    root_endpoint.add_endpoint('/events', endpoint)
    rest_manager = RESTManager(config=config.api, root_endpoint=root_endpoint, state_dir=tmp_path)

    await rest_manager.start()
    yield rest_manager
    await rest_manager.stop()


async def open_events_socket(rest_manager_, connected_event, events_up):
    global messages_to_wait_for
    port = rest_manager_.config.http_port
    url = f'http://localhost:{port}/events'
    headers = {'User-Agent': 'Tribler ' + version_id}

    async with ClientSession() as client:
        async with client.get(url, headers=headers) as response:
            # The first event message is always events_start
            await response.content.readline()
            await response.content.readline()  # Events are separated by 2 newline characters
            connected_event.set()
            while True:
                msg = await response.content.readline()
                await response.content.readline()
                topic_name = json.loads(msg[5:])["topic"]
                messages_to_wait_for.remove(topic_name)
                if not messages_to_wait_for:
                    events_up.set()
                    break


async def test_events(rest_manager, notifier: Notifier):
    """
    Testing whether various events are coming through the events endpoints
    """
    global messages_to_wait_for
    connected_event = Event()
    events_up = Event()
    # await open_events_socket(rest_manager, connected_event, events_up)
    event_socket_task = create_task(open_events_socket(rest_manager, connected_event, events_up))
    await connected_event.wait()

    notifier[notifications.channel_entity_updated]({"state": "Complete"})
    notifier[notifications.watch_folder_corrupt_file]("some_file_name")
    notifier[notifications.tribler_new_version]("1.2.3")
    notifier[notifications.channel_discovered]({"result": "bla"})
    notifier[notifications.torrent_finished]('a' * 10, "torrent_name", False)
    notifier[notifications.low_space]({})
    notifier[notifications.tunnel_removed](circuit_id=1234, bytes_up=0, bytes_down=0, uptime=1000,
                                           additional_info='test')
    notifier[notifications.remote_query_results]({"query": "test"})
    rest_manager.root_endpoint.endpoints['/events'].on_tribler_exception(ReportedError('', '', {}))

    messages_to_wait_for = {
        'channel_entity_updated', 'watch_folder_corrupt_file', 'tribler_new_version', 'channel_discovered',
        'torrent_finished', 'low_space', 'tunnel_removed', 'remote_query_results', 'tribler_exception'
    }

    await events_up.wait()

    event_socket_task.cancel()
    with suppress(CancelledError):
        await event_socket_task


@patch.object(EventsEndpoint, 'write_data')
@patch.object(EventsEndpoint, 'has_connection_to_gui', new=MagicMock(return_value=True))
async def test_on_tribler_exception_has_connection_to_gui(mocked_write_data, endpoint, reported_error):
    # test that in case of established connection to GUI, `on_tribler_exception` will work
    # as a normal endpoint function, that is call `write_data`
    endpoint.on_tribler_exception(reported_error)

    mocked_write_data.assert_called_once()
    assert not endpoint.undelivered_error


@patch.object(EventsEndpoint, 'write_data')
@patch.object(EventsEndpoint, 'has_connection_to_gui', new=MagicMock(return_value=False))
async def test_on_tribler_exception_no_connection_to_gui(mocked_write_data, endpoint, reported_error):
    # test that if no connection to GUI, then `on_tribler_exception` will store
    # reported_error in `self.undelivered_error`
    endpoint.on_tribler_exception(reported_error)

    mocked_write_data.assert_not_called()
    assert endpoint.undelivered_error == endpoint.error_message(reported_error)


@patch.object(EventsEndpoint, 'write_data', new=MagicMock())
@patch.object(EventsEndpoint, 'has_connection_to_gui', new=MagicMock(return_value=False))
async def test_on_tribler_exception_stores_only_first_error(endpoint, reported_error):
    # test that if no connection to GUI, then `on_tribler_exception` will store
    # only the very first `reported_error`
    first_reported_error = reported_error
    endpoint.on_tribler_exception(first_reported_error)

    second_reported_error = ReportedError('second_type', 'second_text', {})
    endpoint.on_tribler_exception(second_reported_error)

    assert endpoint.undelivered_error == endpoint.error_message(first_reported_error)


@patch('asyncio.sleep', new=AsyncMock(side_effect=CancelledError))
@patch.object(RESTStreamResponse, 'prepare', new=AsyncMock())
@patch.object(RESTStreamResponse, 'write', new_callable=AsyncMock)
@patch.object(EventsEndpoint, 'encode_message')
async def test_get_events_has_undelivered_error(mocked_encode_message, mocked_write, endpoint):
    # test that in case `self.undelivered_error` is not None, then it will be sent
    endpoint.undelivered_error = {'undelivered': 'error'}

    await endpoint.get_events(MagicMock())

    mocked_write.assert_called()
    mocked_encode_message.assert_called_with({'undelivered': 'error'})
    assert not endpoint.undelivered_error
