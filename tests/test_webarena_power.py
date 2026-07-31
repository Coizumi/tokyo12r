import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "deploy" / "webarena_power.py"
SPEC = importlib.util.spec_from_file_location("webarena_power", MODULE_PATH)
assert SPEC and SPEC.loader
webarena_power = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = webarena_power
SPEC.loader.exec_module(webarena_power)


class WebArenaPowerTest(unittest.TestCase):
    def test_read_secret_file_accepts_label_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret.txt"
            path.write_text("KEY: abc123\n", encoding="utf-8")

            self.assertEqual(webarena_power.read_secret_file(path), "abc123")

    def test_select_instance_by_name(self):
        instances = [
            {"id": 1, "instance_name": "other"},
            {"id": 2, "instance_name": "tokyo12r-batch-01"},
        ]

        selected = webarena_power.select_instance(instances, "tokyo12r-batch-01", None)

        self.assertEqual(webarena_power.instance_id(selected), "2")

    def test_select_instance_by_id(self):
        instances = [{"id": 3, "instance_name": "tokyo12r-batch-01"}]

        selected = webarena_power.select_instance(instances, None, "3")

        self.assertEqual(webarena_power.instance_name(selected), "tokyo12r-batch-01")

    def test_update_status_treats_already_running_as_success(self):
        original = webarena_power.api_request

        def fake_request(*args, **kwargs):
            raise webarena_power.WebArenaApiError(
                400,
                '{"success":false,"errorMessage":"This instance is already running.","errorCode":"I10016"}',
            )

        webarena_power.api_request = fake_request
        try:
            response = webarena_power.update_status("token", "1", "start")
        finally:
            webarena_power.api_request = original

        self.assertEqual(response["instanceStatus"], "running")


if __name__ == "__main__":
    unittest.main()
