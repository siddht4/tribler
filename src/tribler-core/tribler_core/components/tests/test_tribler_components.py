import pytest

from tribler_core.components.base import Session, SessionError
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.tag.tag_component import TagComponent
from tribler_core.components.torrent_checker import TorrentCheckerComponent
from tribler_core.components.tunnels import TunnelsComponent
from tribler_core.components.upgrade import UpgradeComponent
from tribler_core.components.version_check import VersionCheckComponent
from tribler_core.components.watch_folder import WatchFolderComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

def test_session_context_manager(loop, tribler_config):
    session1 = Session(tribler_config, [])
    session2 = Session(tribler_config, [])
    session3 = Session(tribler_config, [])

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()

    session1.set_as_default()
    assert Session.current() is session1

    with session2:
        assert Session.current() is session2
        with session3:
            assert Session.current() is session3
        assert Session.current() is session2
    assert Session.current() is session1

    Session.unset_default_session()

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()


async def test_REST_component(tribler_config):
    components = [KeyComponent(), RESTComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = RESTComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.rest_manager

        await session.shutdown()


async def test_torrent_checker_component(tribler_config):
    components = [SocksServersComponent(), LibtorrentComponent(), KeyComponent(), RESTComponent(),
                  Ipv8Component(), TagComponent(), MetadataStoreComponent(), TorrentCheckerComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = TorrentCheckerComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.torrent_checker

        await session.shutdown()


async def test_tunnels_component(tribler_config):
    components = [Ipv8Component(), KeyComponent(), RESTComponent(), TunnelsComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = TunnelsComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
        assert comp._ipv8_component

        await session.shutdown()


async def test_upgrade_component(tribler_config):
    components = [KeyComponent(), RESTComponent(), UpgradeComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = UpgradeComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.upgrader

        await session.shutdown()


async def test_version_check_component(tribler_config):
    components = [VersionCheckComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = VersionCheckComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.version_check_manager

        await session.shutdown()


async def test_watch_folder_component(tribler_config):
    components = [KeyComponent(), RESTComponent(), SocksServersComponent(), LibtorrentComponent(),
                  WatchFolderComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = WatchFolderComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.watch_folder

        await session.shutdown()
