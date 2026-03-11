"""Minimal ISAPI client for Phase 1.

Phase 2 extends this class with retry logic, full Digest auth handling,
and additional endpoints. Do not restructure this module when extending.
"""
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager

import httpx

from app.core import inflight


@asynccontextmanager
async def _track_inflight():
    """Context manager to track in-flight ISAPI calls for graceful shutdown."""
    inflight.increment()
    try:
        yield
    finally:
        inflight.decrement()


class ISAPIClient:
    """Minimal ISAPI HTTP client for Hikvision NVR devices.

    Phase 1: GET deviceInfo and GET camera channel list.
    Phase 2: Adds retry, extended Digest auth, arm/disarm operations.
    """

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.base_url = f"http://{host}:{port}"
        self._auth = httpx.DigestAuth(username, password)
        self._client_kwargs: dict = {
            "auth": self._auth,
            "verify": False,  # NVRs commonly use self-signed certs
            "timeout": httpx.Timeout(10.0, connect=5.0, read=10.0),
        }

    async def get_device_info(self) -> dict:
        """GET /ISAPI/System/deviceInfo — returns parsed device info dict."""
        async with _track_inflight():
            async with httpx.AsyncClient(**self._client_kwargs) as client:
                resp = await client.get(f"{self.base_url}/ISAPI/System/deviceInfo")
                resp.raise_for_status()
                return self._parse_xml(resp.text)

    async def get_camera_channels(self) -> list[dict]:
        """GET /ISAPI/System/Video/inputs/channels — returns list of channel dicts."""
        async with _track_inflight():
            async with httpx.AsyncClient(**self._client_kwargs) as client:
                resp = await client.get(
                    f"{self.base_url}/ISAPI/System/Video/inputs/channels"
                )
                resp.raise_for_status()
                return self._parse_channel_list(resp.text)

    def _detection_url(self, channel_no: int, detection_type: str) -> str:
        """Return the ISAPI Smart detection URL for the given channel and type."""
        return f"{self.base_url}/ISAPI/Smart/{detection_type}/channels/{channel_no}"

    async def get_detection_config(self, channel_no: int, detection_type: str) -> str:
        """GET detection config for a channel; retry once on timeout.

        Returns raw XML string on 200. Raises immediately on non-timeout errors.
        On timeout: retries once. Second timeout re-raises TimeoutException.
        """
        url = self._detection_url(channel_no, detection_type)
        async with _track_inflight():
            async with httpx.AsyncClient(**self._client_kwargs) as client:
                try:
                    resp = await client.get(url)
                except httpx.TimeoutException:
                    resp = await client.get(url)
                resp.raise_for_status()
                return resp.text

    async def put_detection_config(
        self, channel_no: int, detection_type: str, xml_body: str
    ) -> None:
        """PUT detection config for a channel; retry once on timeout.

        Returns None on 200. Raises immediately on non-timeout errors.
        On timeout: retries once. Second timeout re-raises TimeoutException.
        """
        url = self._detection_url(channel_no, detection_type)
        async with _track_inflight():
            async with httpx.AsyncClient(**self._client_kwargs) as client:
                try:
                    resp = await client.put(
                        url,
                        headers={"Content-Type": "text/xml"},
                        content=xml_body.encode(),
                    )
                except httpx.TimeoutException:
                    resp = await client.put(
                        url,
                        headers={"Content-Type": "text/xml"},
                        content=xml_body.encode(),
                    )
                resp.raise_for_status()

    def _parse_xml(self, xml_text: str) -> dict:
        """Parse Hikvision XML response into a flat dict (strips namespaces)."""
        root = ET.fromstring(xml_text)
        return {child.tag.split("}")[-1]: child.text for child in root}

    def _parse_channel_list(self, xml_text: str) -> list[dict]:
        """Parse Hikvision channel list XML into list of dicts."""
        root = ET.fromstring(xml_text)
        channels = []
        for ch in root.iter():
            if ch.tag.endswith("VideoInputChannel"):
                id_el = ch.find(".//{*}id")
                name_el = ch.find(".//{*}name")
                if id_el is not None:
                    channels.append(
                        {
                            "channel_no": int(id_el.text),
                            "name": name_el.text if name_el is not None else None,
                        }
                    )
        return channels
