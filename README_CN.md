# LunarSafeMap

面向月球候选着陆区的多源遥感地形安全性与科学价值评价（本科科研训练项目）。
研究对象为 Yang et al. (2026, *Nature Astronomy* 10, 644–654,
doi:10.1038/s41550-026-02790-0) 提出的 Rimae Bode 载人登月候选区
（353–359°E, 8–13°N）。英文版见 [README.md](README.md)。

## 核心科学问题

在不同空间分辨率、地形指标与权重设置下，月球候选着陆区的安全性评价结果是否稳定？
自动撞击坑识别能否提高安全区划分的客观性与可复现性？

三个假设：**H1 分辨率效应**（粗 DEM 高估安全区）、**H2 多源融合效应**
（联合评价优于单一坡度）、**H3 评价不确定性**（固定权重得到的最佳点可能不稳定）。

## 主要结论（第 1–9 周）

| 环节 | 结论 |
|---|---|
| 撞击坑识别 | 测试区像素 IoU 0.298 / F1 0.460，检测级 F1 0.488；≥5 km 的 8 个坑全部检出且零虚警 |
| 人工核查修正 | 随机抽样 40 个虚警 → **精度 0.451 修正为 0.726（0.644–0.807）**；40 个漏检 → **可探测召回 0.717（0.655–0.788）** |
| 适宜性模型 | 等权安全区 58.4 %；作者 AHP 权重（CR = 0.0157）70.7 %；最优候选点 (353.76°E, 11.08°N) 在所有参数化下一致 |
| 文献验证 | 论文四个候选点中 **LS3 在四种参数化下都最安全**（80.6–86.2 分位），**LS2 都最危险**（0.7–1.9 分位） |
| 不确定性 | 安全区比例 5–95 % 区间 **0.38–0.93**，但排序稳健（最优站点每次抽样分位 ≥ 99） |
| 不确定性来源 | **阈值主导**（组间极差 0.15–0.18）≫ 权重 > 撞击坑目录（0.03） |
| 空间格局 | 仅 **26.1 %** 区域在任何参数下都安全，**35.2 %** 取决于参数 |

完整的科学讨论见 [docs/week9_discussion_CN.md](docs/week9_discussion_CN.md)。

## 仓库结构

```text
scripts/    54 个处理脚本（按周编号，完整索引见 docs/script_index.md）
docs/       20 篇方法/复盘文档（中文为主）
configs/    研究区参数、论文候选点、AHP 判断矩阵
tests/      6 个自测脚本（含索引完整性检查）
outputs/    各周产物（CSV / GeoJSON / PNG；大栅格不进 Git，仅登记哈希）
data/       本地数据（原始与中间数据不入库）
```

## 快速开始

```bash
conda env create -f environment.yml          # 需要 GDAL 的地理空间环境（lunarsafe）
conda activate lunarsafe
bash scripts/run_all_tests.sh                # 运行全部自测

# 复现第 7–9 周的核心结果（不需要重新下载原始数据）
python scripts/week7_suitability.py --weights 0.5499,0.2098,0.2402 --tag ahp
python scripts/week7_compare_literature.py --tag ahp
python scripts/week8_montecarlo.py --n 200 --concentration 15 --tag k15
python scripts/week9_case_studies.py --tag k15
```

完整的复现入口（含 ISIS/ASP 立体测图与神经网络训练）见
[docs/reproduction.md](docs/reproduction.md)；工作流图见 [docs/workflow.md](docs/workflow.md)。

## 数据管理原则

大型行星数据（PDS 原始影像、ISIS cube、ASP 输出、模型权重）**不提交到 Git**；
仓库只记录数据来源、产品清单（含大小与 SHA-256）、处理脚本与参数。
溯源信息见 `data/metadata/data_manifest.csv` 与 `data/metadata/derived_products.csv`。

## 引用

引用方式见 [CITATION.cff](CITATION.cff)。代码采用 MIT 许可；第三方数据与软件遵循各自条款。
