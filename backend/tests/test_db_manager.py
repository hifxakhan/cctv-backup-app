import os
import tempfile
import unittest

from app.database.db_manager import DatabaseManager


class DatabaseManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_and_fetch_history(self) -> None:
        self.db.record_upload(
            file_name="sample.mp4",
            file_path="/videos/sample.mp4",
            file_size=1024,
            md5_hash="abc123",
            drive_file_id="drive-1",
            drive_link="https://example.com/1",
        )

        history = self.db.get_upload_history(limit=10, offset=0)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["file_name"], "sample.mp4")

        pending = self.db.get_pending_files()
        self.assertEqual(len(pending), 0)

    def test_stats_range(self) -> None:
        self.db.record_upload(
            file_name="sample.mp4",
            file_path="/videos/sample.mp4",
            file_size=2048,
            md5_hash="abc123",
            drive_file_id="drive-1",
            drive_link="https://example.com/1",
        )
        stats = self.db.get_stats_range(days=7)
        self.assertEqual(stats["total_files"], 1)
        self.assertEqual(stats["total_size_bytes"], 2048)


if __name__ == "__main__":
    unittest.main()
