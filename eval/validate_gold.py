# -*- coding: utf-8 -*-
"""Validate eval/ja_gold.json (schema + reference field completeness)."""
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP = os.path.join(ROOT, "eval", "ja_gold.json")
REQUIRED_DOC = ["doc", "source_pdf", "pages", "title", "authors", "abstract",
                "journal", "year", "volume", "issue", "pages_range", "references"]
REQUIRED_REF = ["num", "authors", "title", "year", "journal", "volume", "issue", "pages", "doi"]

def main():
    with io.open(FP, encoding="utf-8") as f:
        g = json.load(f)
    errors = []
    if g.get("schema_version") != "1.0":
        errors.append("schema_version != 1.0")
    docs = g.get("docs") or []
    seen = set()
    for d in docs:
        name = d.get("doc")
        if not name:
            errors.append("doc without name")
            continue
        if name in seen:
            errors.append("duplicate doc %s" % name)
        seen.add(name)
        for k in REQUIRED_DOC:
            if k not in d:
                errors.append("%s: missing %s" % (name, k))
        if d.get("abstract") and "abstract_en" not in d:
            errors.append("%s: missing abstract_en" % name)
        refs = d.get("references")
        if refs:
            nums = [r.get("num") for r in refs]
            if len(nums) != len(set(nums)):
                errors.append("%s: duplicate ref num" % name)
            for r in refs:
                for k in REQUIRED_REF:
                    if k not in r:
                        errors.append("%s #%s: missing %s" % (name, r.get("num"), k))
                for k in ("title", "authors", "year", "journal"):
                    if not r.get(k):
                        errors.append("%s #%s: empty %s" % (name, r.get("num"), k))
                if not re.fullmatch(r"(19|20)\d{2}", str(r.get("year") or "")):
                    errors.append("%s #%s: bad year %r" % (name, r.get("num"), r.get("year")))
                if r.get("duplicate_of") and r["duplicate_of"] not in nums:
                    errors.append("%s #%s: duplicate_of missing" % (name, r.get("num")))
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("PASS  docs=%d  refs=%d" % (len(docs), sum(len(d.get("references") or []) for d in docs)))
    for d in docs:
        print("  %-9s pages=%-3s abs=%-4d aben=%-4d refs=%-3d %s" % (
            d["doc"], d["pages"], len(d.get("abstract") or ""), len(d.get("abstract_en") or ""),
            len(d.get("references") or []), d.get("references_status")))
    return 0

if __name__ == "__main__":
    sys.exit(main())
