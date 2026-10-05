# 第 9 周：科研解释（论文式讨论稿）

本文档把第 4–8 周的结果转写成论文的语言：方法、结果、讨论、局限、可推广性。
所有数字都来自仓库里的脚本产出，出处列在每节末尾。案例数据来自
`scripts/week9_case_studies.py`（6 项自测）。

---

## 1. 研究问题与假设

> **不同空间分辨率、地形指标与权重设置下，月球候选着陆区的安全性评价结果是否稳定？
> 自动撞击坑识别能否提高安全区划分的客观性与可复现性？**

* **H1 分辨率效应**：低分辨率 DEM 平滑局部坡度与起伏 → 高估安全区面积；
* **H2 多源融合效应**：DEM + 坡度 + 粗糙度 + 撞击坑联合评价优于单一坡度；
* **H3 不确定性**：固定权重得到的"最佳着陆点"可能不稳定；参数扰动后应能识别稳定区域。

研究区：Rimae Bode（353–359°E, 8–13°N），由 Yang et al. (2026, *Nature Astronomy* 10, 644–654,
doi:10.1038/s41550-026-02790-0) 提出为中国首次载人登月优先候选区。

---

## 2. 方法（要点，详见各周文档）

| 环节 | 做法 | 出处 |
|---|---|---|
| DEM | SLDEM2015 裁剪（59.2 m/px，3073×2561）+ 自产 NAC 立体 DEM（3.28 m/px，7×45 km 条带） | 第 4 周 |
| 地形指标 | 60 m 支撑的坡度、粗糙度（3×3 标准差）、起伏度；与第 5 周定义完全一致 | `week5_terrain_metrics.py` |
| 撞击坑 | Robbins (2018) 目录作标签 → U-Net 分割 → 连通域 → 目录（GeoJSON）；**人工随机抽样核查修正精度与召回** | 第 6 周 |
| 适宜性 | `S = w_slope·H_slope + w_rough·H_rough + w_crater·H_crater`，分段线性危险度 | `week7_suitability.py` |
| 候选点 | **5 km 滑窗**按平均 S 排序，取互不重叠的前 N | 同上 |
| 专家权重 | AHP 交互式两两比较 + 一致性比例 CR | `week7_ahp.py` |
| 不确定性 | 200 次 Monte Carlo 扰动（权重、两组阈值、坑缘缓冲、坑目录） | `week8_montecarlo.py` |
| 外部验证 | 与论文 Fig. 5 的 4 个候选点（LS1–LS4）对比 | `week7_compare_literature.py` |

---

## 3. 结果（可直接引用的数字）

1. **撞击坑识别**（第 6 周）：测试区（研究区）像素 IoU 0.298、F1 0.460；检测级 F1 0.488；
   ≥5 km 的 8 个坑全部检出且零虚警。人工核查 40 个随机虚警后，**精度由 0.451 修正为 0.726
   （0.644–0.807）**；40 个随机漏检中 45 % 在 59 m/px 下不可辨认，**可探测召回 0.717
   （0.655–0.788）**，而报告的召回只有 0.533。
2. **适宜性**（第 7 周）：等权下安全区 58.4 %；作者 AHP 权重（0.550/0.210/0.240，CR = 0.0157）
   下 70.7 %；最优候选点 **(353.76°E, 11.08°N)** 在四种参数化下完全一致。
3. **文献验证**（第 7 周）：论文四点在四种参数化下的安全分位——
   **LS3 80.6–86.2 %**、LS1 46.6–65.0 %、LS4 38.3–48.9 %、**LS2 0.7–1.9 %**。
4. **不确定性**（第 8 周）：安全区比例 5–95 % 区间 **0.38–0.93**（宽权重）与 0.44–0.91（≈±30 %）；
   而排名稳健：最优站点在**每一次**抽样中分位 ≥ 99。
   参数主导性：坡度安全阈值 0.177 > 坡度危险阈值 0.161 > 粗糙度危险阈值 0.147 >
   缓冲 0.115 ≫ **坑目录 0.034**；权重中粗糙度相关最强（r = −0.44）。
5. **空间格局**：**26.1 %** 的区域在任何参数下都安全，**35.2 %** 取决于参数，6.3 % 从不安全。

---

## 4. 讨论

### 4.1 失败案例：论文的 LS2 与我们的判定相反（而且是可解释的）

这是全文最值得写的一段：**同一个候选点，论文列为候选，我们的模型判为危险**。

5 km 窗口内的物理量（`outputs/week9/case_sites.csv`）：

| 站点 | 坡度中位数 | 坡度 p95 | 粗糙度中位数 | 粗糙度 p95 | 窗口内已测绘坑数 | 最近坑距 |
|---|---|---|---|---|---|---|
| **LS2** | **9.00°** | **25.64°** | **7.79 m** | **23.16 m** | 2 | 1.55 km |
| LS1 | 2.51° | 20.27° | 2.21 m | 17.94 m | 0 | 2.77 km |
| LS3 | 2.85° | 7.23° | 2.56 m | 5.93 m | 0 | 5.34 km |
| LS4 | 3.52° | 13.91° | 3.09 m | 11.83 m | 1 | 1.64 km |
| Fresh_crater（地标） | 2.14° | 7.28° | 2.00 m | 6.04 m | 1 | 0.12 km |
| **我们的最优区** | **1.51°** | **3.76°** | **1.42 m** | **3.07 m** | 0 | 5.42 km |

**LS2 的坡度中位数（9.0°）是其他三个论文候选点的 2.5–3.6 倍，粗糙度（7.8 m）是 2.5–3.9 倍**，
并且窗口内已有 2 个编目撞击坑、最近一个距中心仅 1.55 km。
也就是说我们的判定与论文的分歧**不是模型噪声，而是可复核的地形事实**。

可能的解释（第 9 周讨论要点）：论文选点综合了**地质样品价值、Th 丰度、玄武岩单元代表性**，
LS2 位于 Rima Bode II 高钍玄武岩单元南侧，科学价值高；
而我们的模型**只看工程安全性**，因此把它排到最后。**这正是"科学价值与工程安全性分离"的定量证据**，
也说明单凭安全性模型不应否定论文的候选点，而应给出"科学价值高但工程风险也高"的标注。

### 4.2 参数敏感区的地貌解释：**它们卡在阈值中间**

| 类别 | 最大连通区面积 | 位置 | 坡度中位数 | 粗糙度中位数 |
|---|---|---|---|---|
| 参数敏感（0.1 < P(safe) < 0.9） | **7,439 km²** | 356.85°E, 10.27°N | **6.16°** | **5.27 m** |
| 稳健安全（P(safe) ≈ 1） | 2,332 km² | 354.26°E, 10.78°N | **1.56°** | **1.55 m** |
| 从不安全（P(safe) ≈ 0） | 104 km² | 358.82°E, 9.00°N | 31.91° | 30.16 m |

敏感区的坡度/粗糙度中位数（6.2°、5.3 m）**恰好落在我们扰动的阈值区间内**
（坡度安全 3–8°、危险 10–20°；粗糙度安全 0.5–2 m、危险 3–10 m），
所以阈值一动，整片区域的分类就翻转。相反，稳健安全区的指标（1.6°、1.6 m）
**远离所有阈值**，从不安全区则是坑内/坑缘（30°、30 m）。

**方法学含义**：敏感性不是随机的，它是"指标落在阈值附近"的必然结果。
在地图上，稳健区与敏感区的边界实际上画出了**阈值在参数空间中的投影**。

### 4.3 外部验证：模型独立地重现了论文的偏好

论文发表时我们并不知道 LS1–LS4 的位置；我们的评价链（DEM → 地形 → 坑目录 → 加权 → 滑窗排序）
独立地给出 **LS3 最安全、LS2 最危险**，且在 200 次参数抽样下不变（LS3 全程 79–88 分位，
LS2 全程 ≤ 4 分位）。这说明该评价链**具备外部可重复性**，而不是只在自身参数下自洽。

### 4.4 局限性（必须写）

1. **只有 3 个因子**：缺少石块丰度（Diviner）与光照层，因此本文的 S 是"三因子安全性"，
   不能称为完整的多准则评价；论文使用的石块丰度是已知的关键危险指标。
2. **撞击坑层的精度非完美**：precision 0.726（0.644–0.807）、可探测召回 0.717（0.655–0.788），
   且基于单次人工判读（n = 40，非完全盲评，作者本人判读，存在确认偏误风险）。
3. **分辨率**：主结果基于 59.2 m/px 的 SLDEM。自产 NAC DEM 只有 3.28 m/px 的 **7×45 km 条带**，
   覆盖研究区约 1 %，且**与前 10 名候选点 0 重叠**——因此 H1 在本研究中**尚未检验**。
4. **阈值主导**：安全区面积对阈值的不确定性（0.15–0.18）远大于对权重（≤0.18，且相关弱）
   与坑目录（0.03）的敏感性。因此本文任何"面积"结论都必须以区间形式给出。
5. **DEM 垂向精度**：SLDEM 在陡坡（>25°）与 NAC 的偏差可达数十米（第 4 周），
   这会影响陡坡区的坡度与粗糙度取值。
6. **未做阈值最优性分析**：本文扰动阈值但未论证哪个阈值才"正确"；工程限制需引用任务规范。

### 4.5 可推广性

* **可推广**：整条流水线（DEM → 多尺度地形指标 → 自动坑目录 → 可配置权重/阈值 → 滑窗候选点 → Monte Carlo）
  不含任何月球专属假设，只要换 DEM 与目录，即可用于火星、水星（如 CTX、MOLA、MESSENGER 数据），
  也可用于地球的选址问题。
* **可推广的结论**：①"面积不确定、排序稳定"这一现象很可能普遍存在，
  因为任何阈值型适宜性模型都有"阈值附近最敏感"的几何性质；
  ②用**排名稳定性**而非单一适宜性图作为交付物，更稳健、也更容易被使用者接受。
* **不可直接推广**：本文的具体阈值、权重与最优坐标只对 Rimae Bode 与所扰动的参数区间成立；
  跨区域使用前必须重跑第 8 周的敏感性分析。

### 4.6 对方法学的三条建议

1. **报告区间，不报告点**：只给一个"安全区占比"会夸大精度；应给出 5–95 % 区间与参数主导性排序。
2. **把敏感区当成产品**：把 P(safe) 落在 0.1–0.9 的区域单独输出，让后续使用者知道
   "这里的结论取决于假设"。
3. **优先论证阈值，而不是权重**：本文显示阈值的影响是权重的数倍；把精力放在工程限制的文献依据上，
   权重的不确定性可以留给 Monte Carlo。

---

## 5. 英文摘要（初稿，供第 10 周修改）

> **Ranking is robust, area is not: a multi-criteria uncertainty analysis of lunar landing-site
> suitability at Rimae Bode.**
> We assess landing-site terrain safety in the Rimae Bode candidate region (353–359°E, 8–13°N)
> by combining SLDEM2015 terrain metrics at 60 m support with an automatically generated crater
> catalogue. Craters are detected with a U-Net trained on the Robbins (2018) catalogue; a manual
> review of 40 randomly sampled false positives raises the detection precision from 0.451 to 0.726
> (0.644–0.807), while a review of 40 randomly sampled misses gives a detectable recall of 0.717
> (0.655–0.788), showing that a substantial part of the apparent error is a property of the
> reference catalogue and of the 59 m DEM, not of the model. Suitability is a weighted sum of
> piecewise-linear hazard layers (slope, roughness, crater proximity) and candidate sites are
> ranked as non-overlapping 5 km windows. Against the four candidate sites of Yang et al. (2026),
> the two independent parameterisations agree on the extremes: LS3 is the safest and LS2 the most
> hazardous of the four under every weight and threshold combination tested. A 200-draw Monte Carlo
> that perturbs weights, thresholds, the crater rim buffer and the crater catalogue shows that the
> *area* of suitable terrain is highly uncertain (5–95 % interval 0.38–0.93) while the *ranking*
> is stable (the top sites stay above the 99th percentile in every draw). Thresholds dominate the
> uncertainty (spread 0.15–0.18 in the safe-area fraction) far more than weights or the crater
> catalogue (0.03), and only 26 % of the study area is safe under every parameter combination
> tested. We therefore recommend reporting suitability as a ranked set of sites with intervals,
> rather than as a single map.

---

## 6. 复现命令

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lunarsafe
cd ~/projects/LunarSafeMap

python scripts/week9_case_studies.py --selftest
python scripts/week9_case_studies.py --tag k15 --top 5
```

产物：`outputs/week9/case_sites.csv`（逐站点地形事实）、
`outputs/week9/case_regions.csv`（敏感/稳健/危险连通区）、
`outputs/week9/case_studies.png`（适宜性图 + P(safe) 图，标注全部站点）。
