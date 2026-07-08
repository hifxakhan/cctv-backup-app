import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.camera.onvif_client import ONVIFCamera


def main() -> None:
    client = ONVIFCamera(
        host=os.getenv("ONVIF_HOST", ""),
        port=int(os.getenv("ONVIF_PORT", "80")),
        username=os.getenv("ONVIF_USER", ""),
        password=os.getenv("ONVIF_PASSWORD", ""),
        days_back=int(os.getenv("ONVIF_DAYS_BACK", "3")),
    )

    print("Configured:", client.is_configured())
    if not client.is_configured():
        print("Set ONVIF_HOST / ONVIF_USER / ONVIF_PASSWORD before testing")
        return

    connected = client.connect()
    print("Connected:", connected)
    if connected:
        print("Profiles:", client.get_profiles())
        print("SD Card Info:", client.get_sd_card_info())
        recordings = client.get_recordings(days_back=client.days_back)
        print("Recordings:", recordings[:5])


if __name__ == "__main__":
    main()
