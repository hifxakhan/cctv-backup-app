from app.camera.onvif_client import ONVIFCamera


def test_onvif_client_reports_unconfigured_when_credentials_missing():
    client = ONVIFCamera(host="", port=80, username="", password="")
    assert client.is_configured() is False
