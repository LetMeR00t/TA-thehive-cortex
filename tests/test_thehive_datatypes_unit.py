import csv
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'tomark',
]

for mod in mocks:
    sys.modules[mod] = MagicMock()

# Add bin and libs to path
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex', 'libs'))

import modalert_thehive_common


class TestCreateDatatypeLookup(unittest.TestCase):
    """The datatype lookup refresh must NEVER lose user-defined custom rows
    (regression test for the v4.1.0 'Smart Sync' overwrite bug)."""

    HEADER = ["field_name", "field_type", "datatype", "description"]

    def setUp(self):
        # Fake SPLUNK_HOME so the lookup path stays inside a temp sandbox
        self.splunk_home = tempfile.mkdtemp()
        self._old_splunk_home = os.environ.get("SPLUNK_HOME")
        os.environ["SPLUNK_HOME"] = self.splunk_home
        self.lookup_dir = os.path.join(
            self.splunk_home, "etc", "apps", "TA-thehive-cortex", "lookups"
        )
        self.lookup_file = os.path.join(self.lookup_dir, "thehive_datatypes.csv")

        self.thehive = MagicMock()
        self.thehive.observable_type.list.return_value = [
            {"name": "ip"},
            {"name": "domain"},
            {"name": "new-custom-type"},
        ]

    def tearDown(self):
        if self._old_splunk_home is None:
            del os.environ["SPLUNK_HOME"]
        else:
            os.environ["SPLUNK_HOME"] = self._old_splunk_home
        shutil.rmtree(self.splunk_home, ignore_errors=True)

    def _write_lookup(self, rows):
        os.makedirs(self.lookup_dir, exist_ok=True)
        with open(self.lookup_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.HEADER)
            writer.writerows(rows)

    def _read_lookup(self):
        with open(self.lookup_file, "rt", newline="") as f:
            return list(csv.DictReader(f))

    def test_creates_lookup_when_missing(self):
        modalert_thehive_common.create_datatype_lookup(self.thehive)

        rows = self._read_lookup()
        self.assertEqual(
            {r["field_name"] for r in rows}, {"ip", "domain", "new-custom-type"}
        )
        self.assertTrue(all(r["field_type"] == "observable" for r in rows))

    def test_no_refresh_without_force_when_file_exists(self):
        self._write_lookup([["src_ip", "observable", "ip", "custom mapping"]])

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=False)

        self.thehive.observable_type.list.assert_not_called()
        rows = self._read_lookup()
        self.assertEqual([r["field_name"] for r in rows], ["src_ip"])

    def test_force_refresh_preserves_custom_rows(self):
        self._write_lookup(
            [
                ["src_ip", "observable", "ip", "custom mapping"],
                ["dest_domain", "observable", "domain", ""],
                ["ip", "observable", "ip", ""],
            ]
        )

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        rows = {r["field_name"]: r for r in self._read_lookup()}
        # Custom rows are untouched
        self.assertEqual(rows["src_ip"]["datatype"], "ip")
        self.assertEqual(rows["src_ip"]["description"], "custom mapping")
        self.assertIn("dest_domain", rows)
        # Only datatypes missing from the lookup are appended
        self.assertIn("new-custom-type", rows)
        self.assertIn("domain", rows)
        # No duplicate for already-known field names
        field_names = [r["field_name"] for r in self._read_lookup()]
        self.assertEqual(len(field_names), len(set(field_names)))

    def test_force_refresh_keeps_file_intact_on_api_failure(self):
        self._write_lookup([["src_ip", "observable", "ip", "custom mapping"]])
        self.thehive.observable_type.list.side_effect = Exception("API down")

        # force=True must not raise and must not touch the file
        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        rows = self._read_lookup()
        self.assertEqual([r["field_name"] for r in rows], ["src_ip"])

    def test_get_datatype_dict_refreshes_old_file_without_losing_rows(self):
        self._write_lookup([["src_ip", "observable", "ip", "custom mapping"]])
        # Make the file look older than 24h to trigger the refresh path
        old_time = os.path.getmtime(self.lookup_file) - 90000
        os.utime(self.lookup_file, (old_time, old_time))

        data_type = modalert_thehive_common.get_datatype_dict(self.thehive)

        self.thehive.observable_type.list.assert_called_once()
        # Custom mapping survived the refresh and is returned to alert actions
        self.assertEqual(data_type["src_ip"], "ip")
        self.assertEqual(data_type["new-custom-type"], "new-custom-type")

    def test_no_leftover_temp_file_after_refresh(self):
        self._write_lookup([["src_ip", "observable", "ip", ""]])

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        leftovers = [f for f in os.listdir(self.lookup_dir) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])


if __name__ == '__main__':
    unittest.main()
