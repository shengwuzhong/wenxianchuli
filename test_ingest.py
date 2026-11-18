# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

import ingest


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


class IngestTest(unittest.TestCase):
    def test_baseline_then_new_file_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = os.path.join(tmp, "uploads")
            os.makedirs(up)
            _write(os.path.join(up, "a.pdf"), b"a")
            store = ingest.IngestStore(os.path.join(tmp, "ingest.json"))
            sc = ingest.IngestScanner(store, up, stable_scans=1,
                                      page_counter=lambda fp: 3)
            ev = sc.scan()
            self.assertEqual([e["status"] for e in ev], ["baseline"])
            self.assertEqual(ev[0]["count"], 1)
            self.assertFalse([e for e in sc.scan() if e["status"] == "pending"])
            _write(os.path.join(up, "b.pdf"), b"b")
            ev = sc.scan()
            self.assertEqual([e["status"] for e in ev], ["pending"])
            self.assertEqual(ev[0]["doc"], "b")
            self.assertEqual(ev[0]["pages"], 3)
            self.assertEqual(store.entry("b.pdf")["status"], "pending")

    def test_new_file_waits_for_stable_scans(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = os.path.join(tmp, "uploads")
            os.makedirs(up)
            _write(os.path.join(up, "seed.pdf"), b"seed")
            store = ingest.IngestStore(os.path.join(tmp, "ingest.json"))
            sc = ingest.IngestScanner(store, up, stable_scans=2, page_counter=lambda fp: 1)
            sc.scan()
            _write(os.path.join(up, "a.pdf"), b"a")
            self.assertEqual(sc.scan(), [])
            self.assertEqual([e["status"] for e in sc.scan()], ["pending"])

    def test_baseline_is_durable_and_new_scanner_does_not_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = os.path.join(tmp, "uploads")
            os.makedirs(up)
            _write(os.path.join(up, "a.pdf"), b"a")
            fp = os.path.join(tmp, "ingest.json")
            s1 = ingest.IngestStore(fp)
            sc1 = ingest.IngestScanner(s1, up, stable_scans=1, page_counter=lambda fp: 1)
            sc1.scan()
            s2 = ingest.IngestStore(fp)
            sc2 = ingest.IngestScanner(s2, up, stable_scans=1, page_counter=lambda fp: 1)
            self.assertEqual(sc2.scan(), [])
            _write(os.path.join(up, "c.pdf"), b"c")
            self.assertEqual([e["status"] for e in sc2.scan()], ["pending"])

    def test_duplicate_sha_is_not_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = os.path.join(tmp, "uploads")
            os.makedirs(up)
            _write(os.path.join(up, "seed.pdf"), b"seed")
            store = ingest.IngestStore(os.path.join(tmp, "ingest.json"))
            sc = ingest.IngestScanner(store, up, stable_scans=1, page_counter=lambda fp: 2)
            sc.scan()                      # baseline: seed
            _write(os.path.join(up, "a.pdf"), b"same")
            self.assertEqual([e["status"] for e in sc.scan()], ["pending"])
            _write(os.path.join(up, "b.pdf"), b"same")
            ev = sc.scan()
            self.assertEqual([e["status"] for e in ev], ["duplicate"])
            self.assertEqual(ev[0]["duplicate_of"], "a.pdf")
            self.assertNotIn("b", [e.get("doc") for e in ev if e["status"] == "pending"])

    def test_changed_same_name_is_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = os.path.join(tmp, "uploads")
            os.makedirs(up)
            fp = os.path.join(up, "a.pdf")
            _write(fp, b"one")
            store = ingest.IngestStore(os.path.join(tmp, "ingest.json"))
            sc = ingest.IngestScanner(store, up, stable_scans=1, page_counter=lambda fp: 2)
            sc.scan()
            _write(fp, b"two")
            ev = sc.scan()
            self.assertEqual([e["status"] for e in ev], ["conflict"])
            self.assertEqual(store.entry("a.pdf")["status"], "conflict")

    def test_unopenable_pdf_is_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = os.path.join(tmp, "uploads")
            os.makedirs(up)
            _write(os.path.join(up, "a.pdf"), b"a")
            store = ingest.IngestStore(os.path.join(tmp, "ingest.json"))
            sc = ingest.IngestScanner(store, up, stable_scans=1, page_counter=lambda fp: 0)
            sc.scan()
            _write(os.path.join(up, "bad.pdf"), b"bad")
            ev = sc.scan()
            self.assertEqual([e["status"] for e in ev], ["bad"])
            self.assertEqual(store.entry("bad.pdf")["status"], "bad")


if __name__ == "__main__":
    unittest.main()
