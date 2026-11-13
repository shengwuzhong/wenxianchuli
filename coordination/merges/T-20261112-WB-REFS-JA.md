# Merge — T-20261112-WB-REFS-JA

- 分支：`agent/workbuddy/main` @ `ed01fc0`（代码 `ddd8621`）
- merge commit：`6b9d1f2`
- tag：`merge-T-20261112-WB-REFS-JA`
- 变更：`metapy/refs.py`、`metapy/common.py`、`regress.py`
- 测试：`metapy.refs` 48/48；`test_pipeline.py` 12/12；`ner_lite` OK；compileall OK
- GT：
  - `2025_1` 35/34，recall 1.000，title 0.912，author 1.000，author 为空 0
  - `52_230725` 7/7，recall 1.000
  - `40_10569` 18/19，recall 0.947（#16 非阻塞）
- 兼容：42_185 18、42_93 49、5_55 33、52_230302 43 不变
- 正式 `out/`：1151 文件，哈希 `09a8820b…` 未变
- Review：`coordination/reviews/T-20261112-WB-REFS-JA.md`（round 3 approve）
