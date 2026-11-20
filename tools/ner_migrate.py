#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ner_migrate.py — NER 产物路径归位的可审计迁移器。

背景(2026-11-20):
  stages._st_ner 曾把"区根" out_llm_trial 传给 ner_lite.write_outputs(dst=...), 而该函数
  把 dst 当最终目录, 产物因此落在 out_llm_trial/<doc>/, 而 ARTIFACTS["ner"] /
  gui._ner_done / entview 只认 out_llm_trial/fds_extract/ner_lite/<doc>/ner_lite.json。
  代码已由 ner_lite._leaf() 修好; 本脚本负责把历史错位产物搬回标准位置, 并留下可比对的凭据。

纪律(这是与"一次性 shutil.move 脚本"的区别):
  1. 写前日志(write-ahead): --apply 时**先**把 {doc, src, dst, 文件清单, 大小, sha256}
     追加进 manifest, 再做 rename; 中途崩溃可凭 manifest 续跑或回退。
  2. 默认 dry-run: 不带 --apply 只打印计划, 不动盘。
  3. 单目录整体 rename, 不逐文件拷贝; 目标已存在一律拒迁(不合并、不覆盖)。
  4. --verify 事后重算 sha256, 证明"内容没被改"; --rollback 按 manifest 逆序搬回。

用法:
  python tools/ner_migrate.py --plan                      # 干跑: 列出待迁条目
  python tools/ner_migrate.py --apply -m m.jsonl          # 执行并写 manifest
  python tools/ner_migrate.py --snapshot -o snap.json     # 对现状做完整性快照(不动盘)
  python tools/ner_migrate.py --verify snap.json          # 按快照重算校验
  python tools/ner_migrate.py --rollback m.jsonl --apply  # 逆序搬回(默认 dry-run)
  python tools/ner_migrate.py --self-test                 # 临时目录内验证全流程
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONE = "out_llm_trial"
LEAF = os.path.join("fds_extract", "ner_lite")
PRODUCT = "ner_lite.json"
SIDECARS = ("ner_lite_audit.json", "_audit.html")


def _hash(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dir_entries(path):
    """目录内文件清单(相对名, 字节, sha256), 按名排序 —— manifest 的最小可比单元。"""
    out = []
    for name in sorted(os.listdir(path)):
        fp = os.path.join(path, name)
        if not os.path.isfile(fp):
            continue
        out.append({"name": name, "bytes": os.path.getsize(fp), "sha256": _hash(fp)})
    return out


def _audit_facts(path):
    """产物自证: audit 里的 doc 字段与目录名是否一致 + 模型/时间(用于判断来源批次)。"""
    fp = os.path.join(path, "ner_lite_audit.json")
    if not os.path.isfile(fp):
        return {}
    try:
        j = json.load(io.open(fp, encoding="utf-8"))
    except Exception as e:
        return {"audit_parse_error": str(e)[:80]}
    return {"audit_doc": j.get("doc"), "model": j.get("model"),
            "generated": j.get("generated"),
            "records": (j.get("counts") or {}).get("records")}


# ---------- 扫描 ----------

def pending(zone):
    """顶层待迁目录: <zone>/<doc>/ 且含 ner_lite.json(仅此类属于错位产物)。

    顶层还有 check3/ diag_*/ trae_* 等评审目录, 一律不碰。
    """
    if not os.path.isdir(zone):
        return []
    leaf = os.path.join(zone, LEAF)
    out = []
    for name in sorted(os.listdir(zone)):
        src = os.path.join(zone, name)
        if not os.path.isdir(src) or name == "fds_extract":
            continue
        if not os.path.isfile(os.path.join(src, PRODUCT)):
            continue
        dst = os.path.join(leaf, name)
        out.append({"doc": name, "src": src, "dst": dst,
                    "files": _dir_entries(src),
                    "blocked": "目标已存在" if os.path.exists(dst) else None})
    return out


def in_place(zone):
    """已在标准位置的条目(快照用)。

    每条给出: doc / dst(当前=目标路径) / candidate_src(若曾被错位写, 当时应在此) /
    src_verified(该 candidate 是否被日志证实; 现状快照一律 false) / 文件数 / 总大小 / 文件清单。
    """
    leaf = os.path.join(zone, LEAF)
    if not os.path.isdir(leaf):
        return []
    out = []
    for name in sorted(os.listdir(leaf)):
        dst = os.path.join(leaf, name)
        if not os.path.isdir(dst) or not os.path.isfile(os.path.join(dst, PRODUCT)):
            continue
        files = _dir_entries(dst)
        out.append({"doc": name, "path": dst, "dst": dst,
                    "candidate_src": os.path.join(zone, name),
                    "src_verified": False,
                    "file_count": len(files),
                    "total_bytes": sum(f["bytes"] for f in files),
                    "files": files,
                    **_audit_facts(dst)})
    return out


# ---------- 迁移 ----------

def apply(items, man_fp, echo=print):
    """写前日志 → rename。返回 (moved, blocked, failed)。"""
    moved, blocked, failed = 0, 0, 0
    if man_fp:
        d = os.path.dirname(man_fp)
        if d and not os.path.isdir(d):
            os.makedirs(d)
    for it in items:
        if it.get("blocked"):
            echo("  拒绝 %s: %s" % (it["doc"], it["blocked"]))
            blocked += 1
            continue
        rec = {"doc": it["doc"], "src": it["src"], "dst": it["dst"],
               "file_count": len(it["files"]),
               "total_bytes": sum(f["bytes"] for f in it["files"]),
               "files": it["files"],
               "started": time.strftime("%Y-%m-%d %H:%M:%S"), "state": "renaming"}
        if man_fp:
            with io.open(man_fp, "a", encoding="utf-8") as f:   # 先落账, 再动手
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            if not os.path.isdir(os.path.dirname(it["dst"])):
                os.makedirs(os.path.dirname(it["dst"]))
            os.rename(it["src"], it["dst"])
            moved += 1
        except Exception as e:
            failed += 1
            echo("  失败 %s: %s" % (it["doc"], str(e)[:100]))
            rec.update(state="failed", error=str(e)[:200])
        else:
            rec.update(state="done", ok=int(time.time()))
            echo("  ✓ %s" % it["doc"])
        finally:
            if man_fp:
                with io.open(man_fp, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return moved, blocked, failed


def rollback(man_fp, dry=True, echo=print):
    """按 manifest 逆序搬回。只处理 state=done 且 src 不存在的条目(幂等)。"""
    recs = [json.loads(l) for l in io.open(man_fp, encoding="utf-8") if l.strip()]
    done = [r for r in recs if r.get("state") == "done"]
    n = 0
    for r in reversed(done):
        if not os.path.isdir(r["dst"]):
            echo("  跳过 %s: 目标已不在(%s)" % (r["doc"], r["dst"]))
            continue
        if os.path.exists(r["src"]):
            echo("  跳过 %s: 源位置已被占用(%s)" % (r["doc"], r["src"]))
            continue
        echo("  %s %s -> %s" % ("回滚" if not dry else "将回滚", r["dst"], r["src"]))
        if not dry:
            os.rename(r["dst"], r["src"])
        n += 1
    return n


# ---------- 快照 / 校验 ----------

def snapshot(zone, out_fp, extra=None, echo=print):
    items = in_place(zone)
    bad_doc = [it["doc"] for it in items
               if it.get("audit_doc") and it["audit_doc"] != it["doc"]]
    try:                                   # 自检在 C: 临时目录, 跨盘 relpath 会抛
        zone_rel = os.path.relpath(zone, ROOT)
    except ValueError:
        zone_rel = zone
    snap = {"kind": "post-state snapshot",
            "zone": zone_rel,
            "taken": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(items),
            "total_files": sum(len(it["files"]) for it in items),
            "total_bytes": sum(f["bytes"] for it in items for f in it["files"]),
            "doc_name_mismatch": bad_doc,
            "items": items}
    if extra:
        snap.update(extra)
    io.open(out_fp, "w", encoding="utf-8").write(
        json.dumps(snap, ensure_ascii=False, indent=1))
    echo("快照 %d 篇 / %d 文件 / %d 字节 → %s" % (
        snap["count"], snap["total_files"], snap["total_bytes"], out_fp))
    if bad_doc:
        echo("  ⚠ 目录名与 audit.doc 不一致 %d 篇: %s" % (len(bad_doc), bad_doc[:5]))
    return snap


def relocate_top(zone, items, man_fp, echo=print):
    """按快照把叶子产物整体搬回顶层(--relocate-top 用): 构造 apply 的入参并复用同一套
    写前日志/拒绝规则。语义 = 撤销"归位", 回到迁移前布局; 再 --apply 可原样搬回来。"""
    plan = []
    for it in items:
        top = os.path.join(zone, it["doc"])
        plan.append({"doc": it["doc"], "src": it["path"], "dst": top,
                     "files": it["files"],
                     "blocked": "顶层同名目录已存在" if os.path.exists(top) else None})
    return apply(plan, man_fp, echo=echo)


def verify(snap_fp, echo=print):
    """按快照重算: 缺失/多出/被改。零差异才算"内容未被触碰"。"""
    snap = json.load(io.open(snap_fp, encoding="utf-8"))
    miss, extra, changed = [], [], []
    for it in snap["items"]:
        p = it.get("path") or it.get("dst")
        if not os.path.isdir(p):
            miss.append(it["doc"])
            continue
        now = {f["name"]: f for f in _dir_entries(p)}
        old = {f["name"]: f for f in it["files"]}
        for name, f in old.items():
            if name not in now:
                changed.append("%s/%s 缺失" % (it["doc"], name))
            elif now[name]["sha256"] != f["sha256"]:
                changed.append("%s/%s 校验和不一致" % (it["doc"], name))
        for name in now:
            if name not in old:
                extra.append("%s/%s" % (it["doc"], name))
    echo("校验: %d 篇; 缺失 %d / 新增 %d / 变更 %d" % (
        len(snap["items"]), len(miss), len(extra), len(changed)))
    for x in (miss + extra + changed)[:10]:
        echo("  - " + x)
    return 0 if not (miss or extra or changed) else 1


# ---------- 自检 ----------

def self_test():
    tmp = tempfile.mkdtemp(prefix="nermig_")
    try:
        zone = os.path.join(tmp, ZONE)
        leaf = os.path.join(zone, LEAF)
        os.makedirs(leaf)
        for doc, flag in (("docA", 1), ("docB", 1), ("docC", 0)):
            base = os.path.join(leaf, doc) if not flag else os.path.join(zone, doc)
            os.makedirs(base)
            io.open(os.path.join(base, PRODUCT), "w", encoding="utf-8").write(
                json.dumps({"doc": doc, "records": []}))
            io.open(os.path.join(base, "ner_lite_audit.json"), "w", encoding="utf-8").write(
                json.dumps({"doc": doc, "model": "mock", "generated": "2026-11-20 00:00",
                            "counts": {"records": 0}}))
        os.makedirs(os.path.join(zone, "check3"))          # 非产物目录: 必须不碰
        items = pending(zone)
        assert [i["doc"] for i in items] == ["docA", "docB"], items
        man = os.path.join(tmp, "m.jsonl")
        moved, blocked, failed = apply(items, man, echo=lambda s: None)
        assert (moved, blocked, failed) == (2, 0, 0), (moved, blocked, failed)
        assert not os.path.isdir(os.path.join(zone, "docA"))
        assert os.path.isfile(os.path.join(leaf, "docA", PRODUCT))
        assert os.path.isdir(os.path.join(zone, "check3"))
        assert pending(zone) == []
        snap = os.path.join(tmp, "s.json")
        s = snapshot(zone, snap, echo=lambda s: None)
        assert s["count"] == 3, s["count"]
        assert s["doc_name_mismatch"] == []
        assert verify(snap, echo=lambda s: None) == 0
        n = rollback(man, dry=True, echo=lambda s: None)
        assert n == 2, n
        n = rollback(man, dry=False, echo=lambda s: None)
        assert n == 2, n
        assert os.path.isfile(os.path.join(zone, "docA", PRODUCT))
        back = pending(zone)                       # 回滚后这两篇回到顶层
        assert [i["doc"] for i in back] == ["docA", "docB"], back
        assert apply(back, os.path.join(tmp, "m2.jsonl"), echo=lambda s: None) == (2, 0, 0)
        assert verify(snap, echo=lambda s: None) == 0     # 回滚往返后逐字节仍一致
        # 快照级"整体搬回顶层"同样可逆: 搬上去再搬下来, 校验和不变
        m, b, f = relocate_top(zone, s["items"], os.path.join(tmp, "m3.jsonl"),
                               echo=lambda s: None)
        assert (m, b, f) == (3, 0, 0), (m, b, f)
        assert os.path.isfile(os.path.join(zone, "docC", PRODUCT))
        up = pending(zone)
        assert len(up) == 3, len(up)
        assert apply(up, os.path.join(tmp, "m4.jsonl"), echo=lambda s: None) == (3, 0, 0)
        assert verify(snap, echo=lambda s: None) == 0
        print("self-test OK: plan/apply/快照/校验/回滚/整体搬回 全通")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NER 产物路径归位(可审计)")
    ap.add_argument("--zone", default=os.path.join(ROOT, ZONE))
    ap.add_argument("--plan", action="store_true", help="干跑, 列计划(默认行为)")
    ap.add_argument("--apply", action="store_true", help="真正执行 rename")
    ap.add_argument("-m", "--manifest", help="write-ahead manifest(jsonl)")
    ap.add_argument("--snapshot", action="store_true", help="对现状做完整性快照")
    ap.add_argument("-o", "--out", help="快照输出路径")
    ap.add_argument("--verify", metavar="SNAP", help="按快照重算校验")
    ap.add_argument("--rollback", metavar="MANIFEST", help="按 manifest 逆序搬回")
    ap.add_argument("--relocate-top", metavar="SNAP",
                    help="按快照把产物整体搬回顶层(撤销归位; 默认干跑)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()
    if a.verify:
        return verify(a.verify)
    if a.rollback:
        n = rollback(a.rollback, dry=not a.apply)
        print(("%s %d 条; 加 --apply 才真正执行" % ("拟回滚" if not a.apply else "已回滚", n)))
        return 0
    if a.relocate_top:
        snap = json.load(io.open(a.relocate_top, encoding="utf-8"))
        items = snap["items"]
        print("拟搬回顶层 %d 篇(目标存在则拒绝)" % len(items))
        if not a.apply:
            for it in items[:5]:
                print("  %s -> %s" % (it["path"], os.path.join(a.zone, it["doc"])))
            print("干跑结束; 加 --apply -m <manifest.jsonl> 执行")
            return 0
        if not a.manifest:
            print("--apply 必须同时给 -m <manifest.jsonl>")
            return 2
        moved, blocked, failed = relocate_top(a.zone, items, a.manifest)
        print("完成: 搬回 %d / 拒绝 %d / 失败 %d" % (moved, blocked, failed))
        return 0 if not failed else 1
    if a.snapshot:
        if not a.out:
            print("--snapshot 需要 -o 输出路径")
            return 2
        snapshot(a.zone, a.out)
        return 0

    items = pending(a.zone)
    print("待迁 %d 篇(顶层 <zone>/<doc>/ 且含 %s)" % (len(items), PRODUCT))
    for it in items[:10]:
        print("  %s -> %s%s" % (it["doc"], it["dst"], "  [拒绝: %s]" % it["blocked"]
                               if it["blocked"] else ""))
    if not a.apply:
        print("干跑结束; 加 --apply -m <manifest.jsonl> 执行")
        return 0
    if not a.manifest:
        print("--apply 必须同时给 -m <manifest.jsonl>(写前日志, 不留就无法审计)")
        return 2
    moved, blocked, failed = apply(items, a.manifest)
    print("完成: 迁移 %d / 拒绝 %d / 失败 %d; manifest=%s"
          % (moved, blocked, failed, a.manifest))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
