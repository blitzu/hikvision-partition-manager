"""Mock ISAPI client for unit tests — avoids real NVR network calls."""


class MockISAPIClient:
    """Drop-in replacement for ISAPIClient during unit tests."""

    def __init__(self, *args, **kwargs) -> None:
        """Accepts (host, port, username, password) to match real ISAPIClient."""
        pass

    async def get_device_info(self) -> dict:
        return {
            "deviceName": "Test-NVR",
            "model": "DS-7616NI",
            "serialNumber": "ABC123",
        }

    async def get_camera_channels(self) -> list[dict]:
        return [
            {"channel_no": 1, "name": "Camera 1"},
            {"channel_no": 2, "name": "Camera 2"},
        ]

    async def get_detection_config(self, channel_no: int, detection_type: str) -> str:
        return "<MotionDetection><enabled>true</enabled></MotionDetection>"

    async def put_detection_config(
        self, channel_no: int, detection_type: str, xml_body: str
    ) -> None:
        return None
