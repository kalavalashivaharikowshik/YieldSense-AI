import threading
import time

import pytest

from ml import model_loader


class FakeDownloader:
    def __init__(self, calls):
        self.calls = calls

    def readinto(self, stream):
        self.calls.append(1)
        stream.write(b"part-1")
        time.sleep(0.05)
        stream.write(b"part-2")


class FakeBlobService:
    calls: list = []
    fail = False

    @classmethod
    def from_connection_string(cls, _):
        return cls()

    def get_blob_client(self, container, blob):
        return self

    def download_blob(self, max_concurrency=1):
        if FakeBlobService.fail:
            raise OSError("network down")

        return FakeDownloader(FakeBlobService.calls)


@pytest.fixture
def fake_storage(tmp_path, monkeypatch):
    FakeBlobService.calls = []
    FakeBlobService.fail = False
    artifact = tmp_path / "model.joblib"
    monkeypatch.setattr(model_loader, "MODEL_ARTIFACT_PATH", artifact)
    monkeypatch.setattr(model_loader, "BlobServiceClient", FakeBlobService)
    monkeypatch.setattr(
        model_loader.settings, "AZURE_STORAGE_CONNECTION_STRING", "fake"
    )

    return artifact


def test_concurrent_downloads_happen_once(fake_storage):
    threads = [
        threading.Thread(target=model_loader._download_model_from_azure)
        for _ in range(5)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(FakeBlobService.calls) == 1
    assert fake_storage.read_bytes() == b"part-1part-2"


def test_failed_download_leaves_no_partial_file(fake_storage):
    FakeBlobService.fail = True

    with pytest.raises(RuntimeError):
        model_loader._download_model_from_azure()

    assert not fake_storage.exists()
    leftovers = [
        path
        for path in fake_storage.parent.iterdir()
        if path.name.startswith(".model-download-")
    ]
    assert leftovers == []
