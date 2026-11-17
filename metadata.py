# -*- coding: utf-8 -*-
r"""M5 元数据字段层 —— `metapy` 包的薄壳(兼容入口, 不是常规入口)。

**常规重跑不要用这个命令。** `python stages.py <doc> <stage>` 已覆盖 m3 / refs / frefs / front /
abs / issue / cspan 全部字段阶段, 而且会校验上游产物、按依赖顺序执行、跑完还能接着建查看器。
这里保留 `metadata.py` 作为兼容入口，并额外支持本地新增的：

    --stage normalize   主字段 normalized + metadata_normalized.json sidecar
    --stage llm         LLM 兜底填空(与启发式结果对比)
    --stage dual        双渠道逐块对比(数据落 out_llm_trial/)
    --stage report      全量字段报告

实现已拆至 `metapy/`: common=共享阈值与工具, m3=跨页拼接, refs=①文献条目, frefs=⑤全部编号脚注,
front=②标题作者机构, abs=③摘要, llmrep=④LLM兜底+报告, cspan=行内引文句,
issue=本篇期刊/年/卷/期/页+关键词。

用法: python metadata.py <doc>... [--out out] [--stage m3|refs|frefs|front|abs|llm|dual|report|cspan|issue|normalize] [--viewer]
实体抽取(基金/软件/数据集)用 ner_lite.py(LLM 提名+程序定位; 产物与审计落 out_llm_trial/fds_extract/ner_lite/)。
"""
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
