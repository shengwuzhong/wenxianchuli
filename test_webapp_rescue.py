import os
import shutil
import tempfile
import time
import unittest

import webapp


class RescueGuardTest(unittest.TestCase):
    def setUp(self):
        with webapp.RESCUE_LOCK:
            webapp.RESCUE_GUARD.clear()

    def test_cooldown_then_cap(self):
        now = time.time()
        self.assertEqual(webapp._rescue_allowed("d", now), (True, ""))
        self.assertEqual(webapp._rescue_mark("d", now), 1)
        self.assertEqual(webapp._rescue_allowed("d", now + 1), (False, ""))

        webapp.RESCUE_GUARD["d"]["next_at"] = 0
        self.assertEqual(webapp._rescue_mark("d", now + 2), 2)
        webapp.RESCUE_GUARD["d"]["next_at"] = 0
        self.assertEqual(webapp._rescue_mark("d", now + 3), 3)

        allowed, why = webapp._rescue_allowed("d", now + 4)
        self.assertFalse(allowed)
        self.assertIn("上限", why)
        self.assertEqual(webapp._rescue_allowed("d", now + 5), (False, ""))  # 只提示一次

    def test_new_doc_is_independent(self):
        now = time.time()
        webapp._rescue_mark("a", now)
        self.assertEqual(webapp._rescue_allowed("b", now), (True, ""))


class RescueScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rescue_test_")
        self.out = os.path.join(self.tmp, "out")
        self.up = os.path.join(self.tmp, "up")
        os.makedirs(os.path.join(self.out, "d", "raw", "mineru"))
        os.makedirs(self.up)
        with open(os.path.join(self.out, "d", "index.html"), "w", encoding="utf-8") as f:
            f.write("x")
        with open(os.path.join(self.up, "d.pdf"), "wb") as f:
            f.write(b"%PDF-1.4")
        with webapp.RESCUE_LOCK:
            webapp.RESCUE_GUARD.clear()
        self.old = (webapp.OUT, webapp.UP, webapp.RESCUE_SCAN_EVERY,
                    webapp._LAST_RESCUE_SCAN, webapp.threading.Thread)
        webapp.OUT, webapp.UP = self.out, self.up
        webapp.RESCUE_SCAN_EVERY = 0
        webapp._LAST_RESCUE_SCAN = 0
        self.submits = []
        self.old_create = webapp._create_job_if_absent
        webapp._create_job_if_absent = self._fake_create

        class FakeThread:
            def __init__(self, *a, **kw):
                pass

            def start(self):
                RescueScanTest.starts += 1

        RescueScanTest.starts = 0
        webapp.threading.Thread = FakeThread

    def tearDown(self):
        webapp.OUT, webapp.UP, webapp.RESCUE_SCAN_EVERY, \
            webapp._LAST_RESCUE_SCAN, webapp.threading.Thread = self.old
        webapp._create_job_if_absent = self.old_create
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_create(self, jid, doc, rescue=""):
        self.submits.append((doc, rescue))
        return True

    def test_scan_submits_same_doc_once(self):
        for _ in range(5):
            webapp._LAST_RESCUE_SCAN = 0
            webapp.rescue_scan()
        self.assertEqual(len(self.submits), 1)
        self.assertEqual(RescueScanTest.starts, 1)


if __name__ == "__main__":
    unittest.main()
