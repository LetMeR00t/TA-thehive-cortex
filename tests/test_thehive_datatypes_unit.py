import csv
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'tomark',
]


# Add bin and libs to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks, remove_tree  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex', 'libs'))

with temporary_mocks(mocks):
    import modalert_thehive_common


class FakeCollectionData:
    """The `.data` of a KV store collection, with the two calls we make.

    ⚠️ `batch_save` is recorded, not merged blindly: the whole point of these
    tests is that a refresh writes ONLY the new rows. A fake that silently
    replaced everything would let the destructive behaviour pass."""

    def __init__(self, rows=None, fail_on_query=False, fail_on_save=False):
        self.rows = list(rows or [])
        self.saved_batches = []
        self.fail_on_query = fail_on_query
        self.fail_on_save = fail_on_save

    def query(self):
        if self.fail_on_query:
            raise Exception("KV store unreachable")
        return [dict(row) for row in self.rows]

    def batch_save(self, *documents):
        if self.fail_on_save:
            raise Exception("KV store read-only")
        self.saved_batches.append([dict(doc) for doc in documents])
        self.rows.extend(dict(doc) for doc in documents)


class FakeKVStore:
    def __init__(self, data):
        self._collections = {modalert_thehive_common.KV_DATATYPES_COLLECTION: data}

    def __getitem__(self, name):
        collection = MagicMock()
        collection.data = self._collections[name]
        return collection


class TestDatatypeLookup(unittest.TestCase):
    """The datatype lookup refresh must NEVER lose user-defined custom rows
    (regression test for the v4.1.0 'Smart Sync' overwrite bug), and the move
    to the KV store must not lose them either."""

    HEADER = ["field_name", "field_type", "datatype", "description"]

    def setUp(self):
        # Fake SPLUNK_HOME so the legacy CSV path stays inside a temp sandbox
        self.splunk_home = tempfile.mkdtemp()
        self._old_splunk_home = os.environ.get("SPLUNK_HOME")
        os.environ["SPLUNK_HOME"] = self.splunk_home
        self.lookup_dir = os.path.join(
            self.splunk_home, "etc", "apps", "TA-thehive-cortex", "lookups"
        )
        self.lookup_file = os.path.join(self.lookup_dir, "thehive_datatypes.csv")

        self.store = FakeCollectionData()
        self.thehive = MagicMock()
        self.thehive.splunk_client.kvstore = FakeKVStore(self.store)
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
        remove_tree(self.splunk_home)

    def _write_legacy_csv(self, rows):
        os.makedirs(self.lookup_dir, exist_ok=True)
        with open(self.lookup_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.HEADER)
            writer.writerows(rows)

    def _stored(self):
        return {row["field_name"]: row for row in self.store.rows}

    def test_fills_empty_collection_from_thehive(self):
        modalert_thehive_common.create_datatype_lookup(self.thehive)

        self.assertEqual(
            set(self._stored()), {"ip", "domain", "new-custom-type"}
        )
        self.assertTrue(
            all(row["field_type"] == "observable" for row in self.store.rows)
        )

    def test_no_refresh_without_force_when_collection_has_rows(self):
        self.store.rows = [
            {"field_name": "src_ip", "field_type": "observable",
             "datatype": "ip", "description": "custom mapping"}
        ]

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=False)

        self.thehive.observable_type.list.assert_not_called()
        self.assertEqual(list(self._stored()), ["src_ip"])

    def test_force_refresh_preserves_custom_rows(self):
        self.store.rows = [
            {"field_name": "src_ip", "field_type": "observable",
             "datatype": "ip", "description": "custom mapping"},
            {"field_name": "dest_domain", "field_type": "observable",
             "datatype": "domain", "description": ""},
            {"field_name": "ip", "field_type": "observable",
             "datatype": "ip", "description": ""},
        ]

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        rows = self._stored()
        # Custom rows are untouched
        self.assertEqual(rows["src_ip"]["datatype"], "ip")
        self.assertEqual(rows["src_ip"]["description"], "custom mapping")
        self.assertIn("dest_domain", rows)
        # Only datatypes missing from the lookup are appended
        self.assertIn("new-custom-type", rows)
        self.assertIn("domain", rows)
        # ⚠️ Nothing already stored is rewritten: a single batch, new rows only
        self.assertEqual(len(self.store.saved_batches), 1)
        self.assertEqual(
            {doc["field_name"] for doc in self.store.saved_batches[0]},
            {"domain", "new-custom-type"},
        )
        field_names = [row["field_name"] for row in self.store.rows]
        self.assertEqual(len(field_names), len(set(field_names)))

    def test_force_refresh_keeps_rows_intact_on_api_failure(self):
        self.store.rows = [
            {"field_name": "src_ip", "field_type": "observable",
             "datatype": "ip", "description": "custom mapping"}
        ]
        self.thehive.observable_type.list.side_effect = Exception("API down")

        # force=True must not raise and must not touch what is stored
        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        self.assertEqual(list(self._stored()), ["src_ip"])
        self.assertEqual(self.store.saved_batches, [])

    def test_unreadable_collection_aborts_rather_than_overwrite(self):
        self.store.fail_on_query = True

        result = modalert_thehive_common.create_datatype_lookup(
            self.thehive, force=True
        )

        self.assertEqual(result, {})
        self.thehive.observable_type.list.assert_not_called()
        self.assertEqual(self.store.saved_batches, [])

    def test_migration_seeds_the_collection_from_the_legacy_csv(self):
        """The rows a user customised under etc/apps must survive the move."""
        self._write_legacy_csv(
            [
                ["src_ip", "observable", "ip", "custom mapping"],
                ["ticket_id", "custom_field", "string", "mine"],
            ]
        )

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        rows = self._stored()
        self.assertEqual(rows["src_ip"]["description"], "custom mapping")
        # A row that is not an observable is migrated just the same
        self.assertEqual(rows["ticket_id"]["field_type"], "custom_field")
        # ... and the migrated names are not re-created from the API
        self.assertIn("new-custom-type", rows)
        self.assertEqual(
            len([r for r in self.store.rows if r["field_name"] == "src_ip"]), 1
        )

    def test_migration_happens_once_and_only_when_empty(self):
        self._write_legacy_csv([["src_ip", "observable", "ip", "from the csv"]])
        self.store.rows = [
            {"field_name": "src_ip", "field_type": "observable",
             "datatype": "ip", "description": "already migrated"}
        ]

        modalert_thehive_common.create_datatype_lookup(self.thehive, force=True)

        self.assertEqual(
            self._stored()["src_ip"]["description"], "already migrated"
        )

    def test_get_datatype_dict_returns_what_the_collection_holds(self):
        self.store.rows = [
            {"field_name": "src_ip", "field_type": "observable",
             "datatype": "ip", "description": "custom mapping"},
            {"field_name": "ticket_id", "field_type": "custom_field",
             "datatype": "string", "description": ""},
        ]

        data_type = modalert_thehive_common.get_datatype_dict(self.thehive)

        # Refreshed once, and the custom mapping survived it
        self.thehive.observable_type.list.assert_called_once()
        self.assertEqual(data_type["src_ip"], "ip")
        self.assertEqual(data_type["new-custom-type"], "new-custom-type")
        # Only observables are part of the mapping alert actions consume
        self.assertNotIn("ticket_id", data_type)

    def test_get_datatype_dict_falls_back_on_api_failure(self):
        self.store.rows = [
            {"field_name": "src_ip", "field_type": "observable",
             "datatype": "ip", "description": "custom mapping"}
        ]
        self.thehive.observable_type.list.side_effect = Exception("API down")

        data_type = modalert_thehive_common.get_datatype_dict(self.thehive)

        self.assertEqual(data_type, {"src_ip": "ip"})

    def test_no_splunk_client_is_reported_not_mistaken_for_empty(self):
        """⚠️ Without a client we cannot know the datatypes; saying "none"
        would silently strip every observable from the payload."""
        self.thehive.splunk_client = None

        self.assertEqual(modalert_thehive_common.get_datatype_dict(self.thehive), {})
        self.thehive.logger_file.error.assert_called()
        self.thehive.observable_type.list.assert_not_called()


if __name__ == '__main__':
    unittest.main()
