# -*- coding: utf-8 -*-
r"""M5 元数据字段层 CLI 入口(实现已拆至 metapy/ 包: common=共享阈值与工具,
m3=跨页拼接, refs=①文献条目, frefs=⑤全部编号脚注, front=②标题作者机构, abs=③摘要,
llmrep=④LLM兜底+报告, cspan=行内引文句, issue=本篇期刊/年/卷/期/页+关键词,
entity=正文/基金/软件/数据集, normalize=metadata_normalized.json sidecar)。
用法不变: python metadata.py <doc>... [--out out] [--stage m3|refs|frefs|front|abs|llm|dual|report|cspan|issue|entity|normalize] [--viewer]
normalize 阶段生成 raw/normalized/map sidecar，不修改 metadata.json。
实体抽取(基金/软件/数据集)用根目录 ner_lite.py(LLM 提名+程序定位; 产物与审计落 out_llm_trial/fds_extract/ner_lite/)。"""
import sys

from metapy import main as metadata_main
from metapy.normalize_meta import main as normalize_main


def _split_normalize(argv):
    """把 `--stage normalize` 从 argv 中剥离；返回 (is_normalize, rest)。"""
    out, i, is_norm = [], 0, False
    while i < len(argv):
        a = argv[i]
        if a == "--stage" and i + 1 < len(argv) and argv[i + 1] == "normalize":
            is_norm = True
            i += 2
            continue
        if a.startswith("--stage=") and a.split("=", 1)[1] == "normalize":
            is_norm = True
            i += 1
            continue
        out.append(a)
        i += 1
    return is_norm, out


if __name__ == "__main__":
    _is_norm, _args = _split_normalize(sys.argv[1:])
    if _is_norm:
        sys.exit(normalize_main(_args))
    metadata_main()
