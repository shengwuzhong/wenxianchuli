# -*- coding: utf-8 -*-
"""P2: per-account Paddle quota and account assignment."""
import json
import os
import tempfile
import unittest

import workbench_state as ws


class QuotaBookTest(unittest.TestCase):
    def test_accounts_are_independent_but_shared_account_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = ws.QuotaBook(os.path.join(tmp, "q.json"), 100)
            a = book.account("paddle_a", 100)
            b = book.account("paddle_b", 100)
            self.assertTrue(a.reserve("A/d1", 60))
            self.assertTrue(b.reserve("B/d2", 60))
            self.assertTrue(a.reserve("A/d2", 30))
            self.assertFalse(a.reserve("A/d3", 20))
            self.assertEqual(a.used(), 90)
            self.assertEqual(b.used(), 60)

            shared = book.account("shared", 100)
            self.assertTrue(shared.reserve("A/x", 60))
            self.assertFalse(shared.reserve("B/y", 60))
            self.assertEqual(shared.used(), 60)

    def test_old_single_account_ledger_migrates(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = os.path.join(tmp, "q.json")
            with open(fp, "w", encoding="utf-8") as f:
                json.dump({"date": __import__("datetime").date.today().isoformat(),
                           "limit": 1000,
                           "entries": {"A/d1": {"pages": 12, "at": "2026-11-18 10:00:00"}}}, f)
            book = ws.QuotaBook(fp, 20000)
            self.assertEqual(book.used("shared"), 12)
            self.assertEqual(book.limit("shared"), 1000)

    def test_daily_roll_clears_entries_but_keeps_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = os.path.join(tmp, "q.json")
            book = ws.QuotaBook(fp, 100)
            a = book.account("paddle_a", 50)
            a.reserve("A/d1", 40)
            book.data["date"] = "2000-01-01"
            book.save()
            self.assertEqual(a.used(), 0)
            self.assertEqual(a.summary()["limit"], 50)


class TaskAccountTest(unittest.TestCase):
    def test_task_keeps_account_across_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = os.path.join(tmp, "state.db")
            st = ws.TaskStore(fp)
            row, _ = st.enqueue("d1", "d1.pdf", ["paddle"], account="paddle_b")
            self.assertEqual(row["account"], "paddle_b")
            self.assertEqual(st.accounts_in_use(), {"paddle_b": 1})
            st.close()
            st2 = ws.TaskStore(fp)   # migration/reopen path
            rows = st2.pending()
            self.assertEqual(rows[0]["account"], "paddle_b")
            st2.close()


class AccountStoreTest(unittest.TestCase):
    def test_bootstrap_assignment_and_delete_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = ws.AccountStore(os.path.join(tmp, "accounts.json"))
            st.bootstrap("abcdefghijklmnop", "主账号")
            self.assertEqual(st.assignment("A"), "primary")
            self.assertEqual(st.assignment("B"), "primary")
            self.assertEqual(st.list_accounts()[0]["token_mask"], "abcd…mnop")
            st.upsert("second", "备用账号", "1234567890abcdef", 5000)
            st.assign("B", "second")
            self.assertEqual(st.assignment("B"), "second")
            ok, msg = st.remove("second")
            self.assertFalse(ok)
            self.assertIn("B", msg)
            st.assign("B", "primary")
            ok, _ = st.remove("second")
            self.assertTrue(ok)
            self.assertEqual(len(st.list_accounts()), 1)

    def test_token_is_not_lost_on_label_or_limit_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = ws.AccountStore(os.path.join(tmp, "accounts.json"))
            st.bootstrap("secret-token-1234")
            st.upsert("primary", "改名", None, 300)
            a = st.get("primary")
            self.assertEqual(a["token"], "secret-token-1234")
            self.assertEqual(a["daily_pages"], 300)
            st.upsert("primary", "改名", "rotated-token-5678", 300)
            self.assertEqual(st.get("primary")["token"], "rotated-token-5678")


if __name__ == "__main__":
    unittest.main()
