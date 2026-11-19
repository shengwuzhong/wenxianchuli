# -*- coding: utf-8 -*-
import io
import json
import os
import tempfile
import unittest

import workbench_runner as wr
import workbench_state as wb


class ScanDocsTest(unittest.TestCase):
    def test_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            z = wb.make_zones(tmp)["A"]
            os.makedirs(z.up, exist_ok=True)
            with io.open(os.path.join(z.up, "paper.pdf"), "wb") as fh:
                fh.write(b"%PDF-1.4\n")
            rows = wr.scan_docs(z)
            self.assertEqual(rows["paper"]["state"], "未跑")

            dd = os.path.join(z.out, "paper")
            for ch in wr.CH:
                os.makedirs(os.path.join(dd, "raw", ch))
                with io.open(os.path.join(dd, "raw", ch, "page_1.json"), "w",
                             encoding="utf-8") as fh:
                    fh.write("{}")
            with io.open(os.path.join(dd, "index.html"), "w", encoding="utf-8") as fh:
                fh.write("ok")
            with io.open(os.path.join(dd, "metadata.json"), "w", encoding="utf-8") as fh:
                json.dump({"title": {"value": "T"}}, fh)
            self.assertEqual(wr.scan_docs(z)["paper"]["state"], "已完成")

            os.remove(os.path.join(dd, "raw", "dots", "page_1.json"))
            os.rmdir(os.path.join(dd, "raw", "dots"))
            rows = wr.scan_docs(z)
            self.assertEqual(rows["paper"]["state"], "部分异常")
            self.assertEqual(rows["paper"]["miss"], ["dots"])


class HubTest(unittest.TestCase):
    def test_accounts_are_assignable(self):
        with tempfile.TemporaryDirectory() as tmp:
            hub = wr.RunnerHub(root=tmp, log=lambda m: None)
            keys = [a["key"] for a in hub.accounts.list_accounts()]
            self.assertTrue(keys)
            hub.set_account("B", keys[0])
            self.assertEqual(hub.zones["B"].account, keys[0])
            self.assertTrue(hub.runners["B"].paused)
            hub.pause_all()
            hub.close()


if __name__ == "__main__":
    unittest.main()
