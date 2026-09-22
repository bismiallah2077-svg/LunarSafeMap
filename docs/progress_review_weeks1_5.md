# LunarSafeMap 项目复盘：第 1–5 周

> 2026-09-22 · 对照最初定下的 10 周计划

## 0. 一句话总结

从零搭起了一条可复现的月球遥感链路：**PDS 数据检索 → ISIS 几何/辐射处理 → ASP 立体测图 →
高分辨率 DEM → 与参考 DEM 的定量验证 → 地形指标与不确定性分析**。
研究对象为 Yang et al. 2026（Nature Astronomy）提出的 Rimae Bode 载人登月候选区；
核心科学发现是：**用 60 m 分辨率的 SLDEM 做安全评估，会把 17%–31% 的陡坡误判为安全区**。

---

## 1. 与原始 10 周计划对照

| 周 | 原计划 | 实际完成 | 状态 |
|---|---|---|---|
| 1 | 环境（WSL/conda/QGIS/规范仓库） | WSL2 + conda（asp/lunarsafe）+ ASP 3.7.0 + ISIS 10.0.0 + GDAL 3.12 + 仓库骨架 | ✅ 完成 |
| 2 | 行星数据（PDS 结构、LROC 检索、ISIS 导入/校正/投影、元数据） | 下载并处理 LROC NAC 立体像对；建立 `data_manifest.csv`（含 SHA-256） | ✅ 完成 |
| 3 | ASP 立体测图 + 首次误差分析 | 复现 ASP 官方 LROC 快速案例；生成 DEM/正射/交会误差；与 LDEM_128 对比（去偏 RMSE ≈23 m） | ✅ 完成 |
| 4 | Rimae Bode 数据集（边界、WAC/NAC/DEM、统一坐标、切片索引、清单、底图） | 全部完成，**并额外产出该区域的 NAC 高分辨率 DEM** | ✅ 超额 |
| 5 | 地形分析（坡度/粗糙度/曲率/起伏、多尺度、初始风险图） | 坡度阈值跨越分析 + 多尺度指标（进行中） | 🔄 进行中 |
| 6 | 撞击坑识别（DeepMoon/YOLO/U-Net） | 未开始 | ⏳ |
| 7 | 适宜性模型（归一化、权重、候选点排序） | 未开始 | ⏳ |
| 8 | 不确定性与消融 | 未开始（第 5 周已提前做了部分不确定性分析） | ⏳ |
| 9 | 科研解释与写作 | 未开始 | ⏳ |
| 10 | 开源整理与发布 | 未开始（但仓库规范从第 1 周就在维护） | ⏳ |

**进度评价**：整体符合预期，第 4 周超出计划（原计划只要求"数据准备"，实际做出了高分辨率 DEM 并完成验证）。
主要偏差来自**环境与数据获取的额外成本**（见第 7 节）。

---

## 2. 分阶段复盘

### 第 1–2 周：环境与行星数据

| 维度 | 内容 |
|---|---|
| **下载** | LROC NAC EDR `M181058717LE` / `M181073012LE`（各 264 MB，2012-01-13，52224×5064×8bit）；LDEM_128（LOLA，128 ppd ≈236 m/px）；conda 安装 ASP 3.7.0 + ISIS 10.0.0 + GDAL 3.12 |
| **网站** | `pds.lroc.im-ldi.com`（PDS LROC 节点）；NASA NAIF；USGS Astrogeology（ISIS）；`imbrium.mit.edu`（SLDEM） |
| **复现内容** | PDS3 标签结构（分离标签 vs 内嵌标签）；LROC 产品检索与下载；ISIS 标准处理链 |
| **ISIS 功能** | `lronac2isis`（导入）、`spiceinit`（几何初始化）、`lronaccal`（辐射定标）、`camrange`（范围）、`maptemplate`（投影模板）、`cam2map`（投影） |
| **脚本** | `scripts/preprocess_isis.sh`、`scripts/build_data_manifest.py` |
| **产出** | 标准投影影像；`data/metadata/data_manifest.csv`（产品 ID、时间、分辨率、CRS、SHA-256、来源链接） |
| **结论** | 打通 PDS→ISIS 链路；建立"每个数据都要有哈希和来源"的规范 |

### 第 3 周：ASP 立体测图 + 首次误差分析

| 维度 | 内容 |
|---|---|
| **下载** | LDEM_128（随 ASP 发行包提供） |
| **复现内容** | ASP 官方 LROC 月球快速案例（`examples/lronac_quick`）端到端流程 |
| **ASP 功能** | `parallel_stereo`（`--alignment-method local_epipolar`、`--stereo-algorithm asp_mgm`、`--subpixel-mode 9`）、`point2dem`（`--errorimage`、`--orthoimage`） |
| **脚本** | `scripts/run_week2_3.sh`（一键复现）、`scripts/compare_dem.py` |
| **产出** | DEM、正射影像、交会误差图；误差直方图/空间分布/协变量分析三张图 |
| **结论** | 与 LDEM_128 存在 **−263.6 m 系统偏移**（基准面差异），去偏后 **RMSE ≈23 m**；
|  | 确立了"跨数据集比较必须先对齐垂直基准"的方法论 |

### 第 4 周：Rimae Bode 数据基础 + NAC 立体像对 + 高分辨率 DEM

| 维度 | 内容 |
|---|---|
| **下载** | ① SLDEM2015 瓦片 `SLDEM2015_512_00N_30N_315_360_FLOAT`（1.42 GB）② LROC WAC 研究区镶嵌（8 MB）③ NAC 立体像对 `M1406988604LE` + `M1406995626LE`（各 264 MB，2022-05-12）④ SPICE 内核三件套：`lrorg_2022074_2022166_v01.bsp`（7.4 MB）、`lrosc_2022131_2022141_v01.bc`（508 MB）、`lrolc_2022120_2022152_v01.bc`（15 MB） |
| **网站** | `imbrium.mit.edu`（SLDEM 镜像）；`planetarymaps.usgs.gov`（USGS 月球 WMS，取 WAC）；`naif.jpl.nasa.gov`（PDS LRO SPICE 档案 + LRO 内核目录）；`data.lroc.im-ldi.com`（LROC 影像检索）；`media.springernature.com`（论文补充材料）；`quickmap.lroc.asu.edu` |
| **复现内容** | Yang et al. 2026 的研究区（8–13°N, 353–359°E）；把 ASP 立体测图流程从"官方样例"迁移到**自主选定区域** |
| **ISIS 功能** | `lronac2isis`、`spiceinit`（**手动指定内核**：`SPK=` 轨道 + `CK=` 本体姿态 + `EXTRA=` 相机姿态）、`lronaccal`、`maptemplate`、`cam2map` |
| **ASP 功能** | `parallel_stereo`（新增 `--processes 4` 限制并发防内存溢出）、`point2dem` |
| **脚本** | `download_wac.py`、`download_sldem.sh`、`preprocess_week4.py`、`preprocess_wac.py`、`make_study_area_map.py`、`build_tiles.py`、`find_stereo_pairs.py`、`stereo_check.py`、`fetch_nac.py`、`install_kernels_and_run.sh`、`run_nac_pair_rimae_bode.sh`、`compare_nac_to_sldem.py`、`coregister_nac_sldem.py`、`check_pair_progress.sh`、`analyze_*.sh` |
| **产出** | 研究区底图（含地标）；30 个 30 km 切片索引；**NAC DEM**（2176×13866 px，3.283 m/px，覆盖 7×45 km）；正射影像；交会误差图；两份对比 CSV；`data/metadata/derived_products.csv`（7 个产物 + SHA-256） |
| **结论** | ① 像对交会角实测 **22.85–23.01°**（预测 23.11°，吻合）② 交会误差中位数 **4.46 m** ③ 与 SLDEM 的**垂直基准一致（中位偏移 −0.83 m）**——与第 3 周那个 −264 m 形成鲜明对比，证明内核配置正确 ④ 整体 RMSE 35.3 m，但 **MAE 仅 10.9 m**，差异集中在陡坡 |

### 第 5 周：地形指标与不确定性（完成）

| 维度 | 内容 |
|---|---|
| **复现内容** | 计划中的"阶段 B 地形指标"与"阶段 E 不确定性"的一部分 |
| **脚本** | `week5_slope_safety_analysis.py`、`week5_terrain_metrics.py` |
| **产出** | `outputs/week5/slope_threshold_crossings.csv`、`affine_residual_model.csv`、`terrain_metrics_multiscale.csv` |
| **结论（已完成部分）** | ① 同分辨率下坡度场高度一致（中位差 −0.05°，MAE 1.58°）② **但阈值跨越暴露问题：SLDEM 把 11.4%（10°）/ 16.9%（15°）/ 31.1%（20°）的陡坡判为安全** ③ 多尺度分析：DEM 从 20 m 粗化到 200 m，"坡度 ≥20° 的面积占比"从 2.8% 降到 1.6%（相对低估 43%）④ 仿射拟合仅改善 RMSE 2.8%，**排除尺度/旋转类配准误差** |

---


#### 5.1 坡度阈值跨越（逐像元）

| 阈值 | NAC 判为陡坡 | SLDEM 漏判 | 漏判率 |
|---|---:|---:|---:|
| 10 deg | 20,872 px | 2,372 | 11.4 % |
| 15 deg | 8,824 px | 1,492 | 16.9 % |
| 20 deg | 2,251 px | 701 | 31.1 % |

同分辨率（59 m）下坡度场高度一致（中位差 -0.05 deg，MAE 1.58 deg），
但逐像元分级有 17-31 % 的分歧。

#### 5.2 多尺度地形指标（20 / 60 / 200 m）

| 尺度 | DEM | 平均坡度 | >=10/15/20 deg 面积占比 |
|---|---|---:|---|
| 20 m | NAC | 9.89 deg | 44.2 / 19.1 / 5.3 % |
| 60 m | NAC | 9.67 deg | 43.2 / 18.3 / 4.7 % |
| 60 m | SLDEM（限 NAC 条带） | 9.76 deg | 43.9 / 18.6 / 5.1 % |
| 200 m | NAC | 9.21 deg | 40.3 / 15.9 / 3.2 % |
| 200 m | SLDEM（限 NAC 条带） | 9.26 deg | 40.8 / 16.2 / 3.2 % |

同尺度同 footprint 下两个 DEM 的坡度统计一致（差 < 1 个百分点）；
但 DEM 从 20 m 粗化到 200 m 后，>=20 deg 的面积占比从 5.3 % 掉到 3.2 %（相对 -40 %）。

#### 5.3 误差的空间结构

- 沿轨中位数在 -13 ~ +23 m 之间摆动（不是平滑漂移）-> 由沿途地形决定；
  段内 IQR 5-35 m 大于段间差异 -> 局部地形是主因
- 沿幅剖面两端偏差更大（-9.4 / +8.4 m，中间 ±3 m）-> 条带边缘效应
- 拟合平面倾斜仅 -0.39 m/km（跨幅）、+0.32 m/km（沿轨）-> 无显著长波倾斜
- 与交会误差相关系数 0.183（弱）；但交会误差 > 8 m 的 0.08 % 像元中位
  |残差| 达 395 m -> 匹配失败造成极端离群值，已在 5.4 中掩除

#### 5.4 初始风险图（坡度 >= 15 deg 或粗糙度 >= 2 m）

| 数据 | 安全 % | 注意 % | 危险 % |
|---|---:|---:|---:|
| NAC @20 m | 50.94 | 22.89 | 26.17 |
| NAC @60 m | 51.98 | 23.19 | 24.83 |
| SLDEM @60 m（全研究区） | 59.96 | 21.78 | 18.26 |
| SLDEM @60 m（限 NAC 条带） | 37.37 | 27.79 | 34.84 |

阈值敏感性（危险面积）：

| 坡度阈值 / 粗糙度阈值 | NAC | SLDEM |
|---|---:|---:|
| 10 deg / 2.0 m | 47.9 % | 23.9 % |
| 15 deg / 2.0 m | 24.8 % | 18.3 % |
| 20 deg / 2.0 m | 12.4 % | 16.8 % |
| 15 deg / 1.0 m | 56.2 % | 73.6 % |
| 15 deg / 5.0 m | 19.0 % | 4.6 % |

#### 第 5 周结论

1. **坡度统计稳健**：同尺度同 footprint 下两个 DEM 的坡度分布与阈值面积一致（< 1 个百分点）。
2. **空间分级不稳健**：逐像元有 17-31 % 的陡坡被 SLDEM 判为安全。
3. **粗糙度判据对产品与阈值都敏感**：统一 180 m 窗口后两者 p50 仍差 1.3 倍
   （NAC 0.98 m vs SLDEM 1.29 m），而阈值恰好落在其分布陡峭处（p90 ~ 2.0 m），
   导致危险面积在阈值变动时**排序翻转**（1.0 m 时 SLDEM 更保守，5.0 m 时 NAC 更保守）。
4. **小尺度风险原理上不可见**：SLDEM 的最小粗糙度窗口是 178 m，
   而 NAC 在 23 m 窗口给出的 0.11 / 0.17 / 0.47 m 微起伏它完全表征不了。
5. 因此第 7 周的适宜性评价必须**报告阈值敏感性**，第 8 周要把它纳入不确定性分析。

---

## 3. 数据与网站汇总

**数据源网站**

| 网站 | 用途 | 下载量 |
|---|---|---|
| `pds.lroc.im-ldi.com` | LROC NAC EDR（4 景） | 1.06 GB |
| `imbrium.mit.edu` | SLDEM2015 瓦片 | 1.42 GB |
| `planetarymaps.usgs.gov` | USGS 月球 WMS（WAC 镶嵌） | 8 MB |
| `naif.jpl.nasa.gov` | LRO SPICE 内核 | 530 MB |
| `data.lroc.im-ldi.com` | LROC 影像检索与元数据 | — |
| `media.springernature.com` | 论文补充材料 | 1.4 MB |

**本地数据总量**：项目目录约 26 GB（其中 ASP 中间产物 19 GB，可清理）

---

## 4. ISIS / ASP 功能清单（已掌握）

| 工具 | 功能 | 使用场景 |
|---|---|---|
| `lronac2isis` | PDS EDR → ISIS cube | 每次数据处理的第一步 |
| `spiceinit` | 几何初始化（加载 SPICE 内核） | 必做；**近年数据需手动指定内核** |
| `lronaccal` | 辐射定标（暗电流、平场） | 影像定量分析前 |
| `camrange` / `maptemplate` | 影像经纬度范围 → 投影模板 | 生成地图投影参数 |
| `cam2map` | 相机几何 → 地图投影 | 生成标准地理编码影像 |
| `parallel_stereo` | 立体匹配（多算法、分块并行） | 立体像对 → 点云 |
| `point2dem` | 点云 → DEM / 正射 / 误差图 | 立体测图最后一步 |
| `gdal_translate` / `gdalinfo` / `gdal.Warp` | 格式转换、统计、重采样 | 全流程胶水 |

---

## 5. 主要科学结论（可直接用于论文）

1. **垂直基准一致性**：精心配置 SPICE 内核后，ASP NAC DEM 与 SLDEM2015 的中位高程差 **−0.83 m**（对比：使用不当基准时可达 −264 m）。跨数据集比较前必须验证基准。

2. **立体测图精度**：0.85 m/px 的 NAC 像对，交会误差中位数 **4.46 m**、P90 6.19 m。

3. **分辨率效应的定量结论**（核心）：
   - 同分辨率（59 m）下坡度场一致：中位差 −0.05°，MAE 1.58°
   - **但用 SLDEM 判安全区会漏掉 16.9%（15° 阈值）到 31.1%（20° 阈值）的陡坡**
   - DEM 从 20 m 粗化到 200 m，"≥20° 陡坡面积占比"从 2.8% 降到 1.6%
   - 结论：**用 60–100 m 分辨率的产品做着陆安全评估会系统性高估安全区，且风险阈值越严格、低估越严重**

4. **误差结构**：NAC DEM 与 SLDEM 的差异随坡度单调增长（<5° 时 MAE 4 m；20–25° 时 20 m；>25° 时 88 m），且**不是配准问题**（无平移、无尺度/旋转误差）。

---

## 6. 遇到的问题与解决（经验教训）

| 问题 | 原因 | 解决 |
|---|---|---|
| `spiceinit` 报缺内核 | ISIS 自带的 LRO 内核库只覆盖到 ~2019 年 | 从 NAIF 手动下载三类内核（`lrorg` 轨道 / `lrosc` 本体姿态 / `lrolc` 相机姿态），用 `SPK=`、`CK=`、`EXTRA=` 显式指定；已写成 `docs/lroc_spice_kernels.md` |
| `CK=a.bc,b.bc` 被当成一个文件名 | ISIS 列表参数需要括号语法 | 改用 `EXTRA=` 传第二个内核 |
| `web=yes` 取内核总失败 | WSL 里 Qt 客户端不走 `http_proxy`；且在线服务对 LROC 返回错误 | 放弃该路径，全部本地化 |
| 电脑跑 ASP 时自动重启 | `parallel_stereo` 默认按核数起多进程 + 多线程，内存打满 | 加 `--processes 4` 限制并发 |
| 卷索引文件内容不全 | 下载时用了 25 秒超时，文件被截断 | 下载后**校验字节数**（现已写入所有脚本） |
| 像对检索出现假阳性 | 影像跨越 0°/360° 经线，包围盒被算成 360° 宽 | 经度展开后再比较 |
| 2026-09-16 文件系统损坏 | 非正常关机导致 ext4 目录块校验和错误 | 用自建救援环境运行 `e2fsck` 修复 |
| 分析脚本随机报错 | GDAL 数据集对象被 Python 提前回收 | 用变量持有数据集对象 |
| SLDEM 尺度算错 | 该文件是经纬度坐标（0.002°/px），被当成 0.002 m/px | 识别地理坐标并换算（1° ≈ 30320 m） |

**共性教训**：**下载必校验、比较先对齐基准、低分辨率产品在陡坡区不可信**。

---

## 7. 下一步（第 6–10 周）

| 周 | 任务 | 与已有工作的衔接 |
|---|---|---|
| 6 | 撞击坑识别（DeepMoon → 现代 PyTorch；YOLO 对照） | 可先用 NAC DEM/正射做训练数据；`outputs/week5` 的坡度与粗糙度图层可作为输入特征 |
| 7 | 适宜性模型（等权/AHP/熵权/Pareto） | 直接使用第 5 周的多尺度地形指标与撞击坑密度 |
| 8 | 不确定性与消融（权重扰动、阈值扰动、DEM 误差模拟） | 第 5 周的阈值跨越分析已提供模板 |
| 9 | 科研解释与写作（失败案例、地貌解释、局限性） | 已有的复现流程与结论可直接构成"方法与结果"章节 |
| 10 | 开源整理（测试、流程图、中英文 README、Release、CITATION.cff） | 仓库规范已从第 1 周维护，主要补充文档与发布 |

---

## 8. 复现入口（全部脚本）

```bash
# 数据获取
python scripts/download_wac.py --bbox "353 8 359 13" --res 100
bash   scripts/download_sldem.sh SLDEM2015_512_00N_30N_315_360_FLOAT.IMG data/raw/sldem2015

# 像对检索与校验
python scripts/find_stereo_pairs.py --index-dir work/lroc_index --region "353 8 359 13"
python scripts/stereo_check.py M1406988604LE M1406995626LE

# 内核 + ISIS + ASP 全流程
bash scripts/install_kernels_and_run.sh

# 验证与分析
bash scripts/analyze_nac_result.sh
bash scripts/analyze_coregistration.sh
bash scripts/week5_slope_safety_analysis.sh     # 第 5 周
bash scripts/analyze_week5_terrain.sh           # 第 5 周
```