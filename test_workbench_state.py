# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest

import workbench_state as ws


class ZoneTest(unittest.TestCase):
    def test_two_physical_zones(self):
        with tempfile.TemporaryDirectory() as root:
            zones = ws.make_zones(root)
            self.assertNotEqual(zones["A"].out, zones["B"].out)
            self.assertTrue(os.path.isdir(zones["B"].up))
            self.assertTrue(os.path.isdir(zones["B"].out))
            self.assertTrue(os.path.isdir(zones["B"].arch))


class TaskStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ws.TaskStore(os.path.join(self.tmp.name, "s.db"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_enqueue_dedupe_and_resume(self):
        row, dup = self.store.enqueue("d1", "d1.pdf", ["mineru"], pages=12)
        self.assertIsNotNone(row)
        self.assertIsNone(dup)
        row2, dup2 = self.store.enqueue("d1", "d1.pdf", ["mineru"])
        self.assertIsNone(row2)
        self.assertEqual(dup2["id"], row["id"])
        self.store.mark_running(row["id"])
        self.assertEqual(self.store.mark_interrupted_running(), 1)
        pending = self.store.pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["status"], "interrupted")
        self.store.requeue(row["id"])
        self.assertEqual(self.store.pending()[0]["status"], "queued")
        self.store.mark_running(row["id"])
        self.store.finish(row["id"], True)
        self.assertEqual(self.store.counts().get("done"), 1)

    def test_queue_survives_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = os.path.join(tmp, "restart.db")
            s1 = ws.TaskStore(fp)
            row, _ = s1.enqueue("d2", "d2.pdf", ["mineru"], pages=7)
            s1.mark_running(row["id"])
            s1.close()
            s2 = ws.TaskStore(fp)
            try:
                self.assertEqual(s2.mark_interrupted_running(), 1)
                pending = s2.pending()
                self.assertEqual(pending[0]["doc"], "d2")
                self.assertEqual(pending[0]["status"], "interrupted")
                self.assertEqual(pending[0]["pages"], 7)
            finally:
                s2.close()


class PidTest(unittest.TestCase):
    def test_current_pid_alive(self):
        self.assertTrue(ws.pid_alive(os.getpid()))
        self.assertFalse(ws.pid_alive(99999999))


class SnapshotTest(unittest.TestCase):
    def test_snapshot_is_point_in_time_and_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            zone = ws.make_zones(tmp)["B"]
            ddir = os.path.join(zone.out, "d1")
            os.makedirs(ddir)
            fp = os.path.join(ddir, "metadata.json")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write("old")
            snap = ws.snapshot_doc(zone, "d1", "test", keep=2)
            self.assertTrue(os.path.isdir(snap))
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write("new")
            with open(os.path.join(snap, "metadata.json"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "old")
            ws.snapshot_doc(zone, "d1", "test2", keep=2)
            ws.snapshot_doc(zone, "d1", "test3", keep=2)
            base = os.path.join(zone.root, "versions", "d1")
            self.assertEqual(len([x for x in os.listdir(base)
                                  if os.path.isdir(os.path.join(base, x))]), 2)


class QuotaStoreTest(unittest.TestCase):
    def test_shared_account_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = ws.QuotaStore(os.path.join(tmp, "q.json"), "shared", 100)
            self.assertTrue(q.reserve("A/d1", 60))
            self.assertTrue(q.reserve("B/d2", 30))
            self.assertFalse(q.reserve("B/d3", 20))
            self.assertEqual(q.used(), 90)
            self.assertEqual(q.remaining(), 10)
            q.release("A/d1")
            self.assertTrue(q.reserve("B/d3", 20))
            self.assertEqual(q.used(), 50)
            q.data["date"] = "2000-01-01"
            q._save()
            self.assertTrue(q.reserve("B/d4", 10))
            self.assertEqual(q.used(), 10)


class EntityStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zone = ws.make_zones(self.tmp.name)["B"]

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, doc, records, counts=None):
        d = os.path.join(self.zone.ner, "fds_extract", "ner_lite", doc)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "ner_lite.json"), "w", encoding="utf-8") as fh:
            json.dump({"doc": doc, "records": records}, fh, ensure_ascii=False)
        with open(os.path.join(d, "ner_lite_audit.json"), "w", encoding="utf-8") as fh:
            json.dump({"doc": doc, "counts": counts or {}}, fh, ensure_ascii=False)

    def test_missing_product_is_not_checked(self):
        st = ws.entity_statuses("none", self.zone)
        self.assertTrue(all(v["status"] == "not_checked" for v in st.values()))

    def test_present_and_absent(self):
        self._write("d1", [{"kind": "software", "name": "SPSS"}],
                    {"errors_network": 0, "dropped_parse_fail": 0})
        st = ws.entity_statuses("d1", self.zone)
        self.assertEqual(st["software"]["status"], "present")
        self.assertEqual(st["dataset"]["status"], "absent_confirmed")

    def test_network_error_is_failed(self):
        self._write("d2", [], {"errors_network": 1, "dropped_parse_fail": 0})
        st = ws.entity_statuses("d2", self.zone)
        self.assertEqual(st["funding"]["status"], "extraction_failed")


if __name__ == "__main__":
    unittest.main()
