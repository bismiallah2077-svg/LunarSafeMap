# 脚本总索引（每个脚本属于哪一周、做什么）

这份索引回答一个具体问题：**GitHub 上到底有没有第 1 周到现在的全部脚本？**
答案是**有**，但早期脚本没有 `weekN_` 前缀，所以按文件名浏览时会误以为
"只有从 week5 开始的脚本"。

内容由 `git log --diff-filter=A` 追出每个文件的**首次提交日期**，
再按项目的 10 周计划归类。`tests/test_script_index.py` 会检查
"任何被 git 跟踪的脚本都必须出现在本文件里"，所以这份索引不会过期。

| 汇总 | 数量 |
|---|---|
| `scripts/` 下脚本 | 45（截至第 6 周推送的 `16690df`）+ 第 7 周新增 2 |
| `tests/` 下测试 | 4 |
| `configs/` 下配置 | 3 |

---

## 第 1–2 周：环境、PDS 数据、ISIS 基础流程

| 脚本 | 首次提交 | 作用 |
|---|---|---|
| `run_week2_3.sh` | 2026-08-17 | 第 2–3 周一键流程（ISIS 导入 → 校正 → 投影 → ASP） |
| `preprocess_isis.sh` | 2026-08-17 | ISIS 批量预处理（lronac2isis / spiceinit / lronaccal / cam2map） |
| `run_pipeline_detached.sh` | 2026-08-17 | 长任务后台运行 + 日志（断电可续跑） |
| `build_data_manifest.py` | 2026-08-17 | 生成 `data/metadata/data_manifest.csv`（ID/分辨率/CRS/时间/哈希/链接） |
| `fetch_nac.py` | 2026-09-18 | 从 PDS 检索并下载 LROC NAC EDR |
| `search_lroc.py` | 2026-09-18 | LROC 产品检索辅助 |
| `fetch_lroc_kernels.sh` | 2026-09-22 | 按年份下载 SPICE 内核（SPK/CK） |
| `install_kernels_and_run.sh` | 2026-09-22 | 内核安装 + 流程串联（浏览器下载的文件自动就位） |
| `download_sldem.sh` | 2026-09-18 | SLDEM2015 下载 + 字节数校验 |
| `download_wac.py` | 2026-09-18 | LROC WAC 镶嵌图（USGS Moon WMS） |
| `preprocess_wac.py` | 2026-09-18 | WAC 投影到月球 CRS |
| `push_and_report.sh` | 2026-09-22 | 推送 + 本地/远端状态报告（直连失败自动走代理） |
| `cleanup_stray_files.sh` | 2026-09-22 | 清理误重定向产生的垃圾文件 |
| `backup_to_windows.sh` | 2026-10-02 | **单向备份**：仓库 → C 盘 `backup_repo/`（不再反向覆盖） |

## 第 3 周：ASP 官方月球案例 + 首次误差分析

| 脚本 | 首次提交 | 作用 |
|---|---|---|
| `run_lronac_quick_example.sh` | 2026-07-20 | ASP 官方月球快速案例（仓库里最早的脚本） |
| `compare_dem.py` | 2026-08-17 | ASP DEM vs 参考 DEM：偏移、RMSE、空间分布 |

## 第 4 周：Rimae Bode 数据基础 + 首对 NAC 立体 DEM

| 脚本 | 首次提交 | 作用 |
|---|---|---|
| `preprocess_week4.py` | 2026-09-18 | 研究区 DEM 裁剪 + km→m 统一单位 |
| `make_study_area_map.py` | 2026-09-18 | 研究区底图（含地标撞击坑） |
| `build_tiles.py` | 2026-09-18 | 切片索引（供第 6 周使用） |
| `find_stereo_pairs.py` | 2026-09-22 | 扫描 LROC 卷索引寻找立体像对 |
| `stereo_check.py` | 2026-09-19 | 像对收敛角/重叠/质量校验 |
| `run_nac_pair_rimae_bode.sh` | 2026-09-22 | ISIS + ASP 全流程（`parallel_stereo` + `point2dem`） |
| `check_pair_progress.sh` | 2026-09-22 | 中断续跑与进度检查 |
| `compare_nac_to_sldem.py` | 2026-09-22 | NAC DEM vs SLDEM2015 统计（全分辨率 + 分辨率匹配） |
| `coregister_nac_sldem.py` | 2026-09-22 | 配准检验、最小二乘残差模型、坡度依赖 |
| `analyze_nac_result.sh` | 2026-09-22 | 结果健康检查包装脚本 |
| `analyze_coregistration.sh` | 2026-09-22 | 配准分析包装脚本 |
| `week4_finalize.sh` | 2026-09-22 | 打包、登记产物哈希、推送 |

## 第 5 周：地形指标、坡度安全性与不确定性

| 脚本 | 首次提交 | 作用 |
|---|---|---|
| `week5_terrain_metrics.py` | 2026-09-22 | 多尺度（20/60/200 m）坡度、曲率、粗糙度、起伏度 |
| `week5_slope_safety_analysis.py` | 2026-09-22 | 坡度阈值交叉统计（SLDEM 漏掉多少陡坡） |
| `week5_error_spatial.py` | 2026-09-22 | 误差空间结构（沿轨/跨轨剖面、残差图） |
| `week5_risk_map.py` | 2026-09-22 | 首版风险图 + 阈值扫描 |
| `analyze_week5_terrain.sh` | 2026-09-22 | 包装：地形指标 |
| `analyze_week5_error.sh` | 2026-09-22 | 包装：误差空间 |
| `analyze_week5_risk.sh` | 2026-09-22 | 包装：风险图 |
| `week5_finalize.sh` | 2026-09-22 | 打包、登记产物、推送 |

## 第 6 周：撞击坑自动识别（U-Net）与人工核查

| 脚本 | 首次提交 | 作用 |
|---|---|---|
| `week6_build_crater_labels.py` | 2026-09-22 | Robbins 2018 目录 → 研究区/训练区子集 → 圆盘掩膜 |
| `week6_build_labels.sh` | 2026-09-22 | 包装（优先使用浏览器下载的 zip） |
| `week6_train_unet.py` | 2026-09-22 | U-Net 训练/评估/全幅预测，支持 1/2/3 输入通道 |
| `week6_ablation.sh` | 2026-09-22 | 输入特征消融（DEM / +坡度 / +坡度+阴影） |
| `week6_ablation_summary.py` | 2026-09-22 | 消融结果汇总表 + 柱状图 |
| `week6_mask_to_catalog.py` | 2026-09-22 | 掩膜 → 连通域 → 撞击坑目录 + 检测级指标（可扫描尺寸阈值） |
| `week6_review_false_positives.py` | 2026-09-22 | 人工核查工具：随机抽样、Wilson 区间、统计修正（第 6 周核心） |
| `week6_show_sample.py` | 2026-10-02 | 教学：把"一个样本"画出来（输入/标签/预测） |
| `week6_finalize.sh` | 2026-09-22 | 打包 + 登记产物 + 推送 |
| `week6_review_finalize.sh` | 2026-10-02 | 核查结果的打包推送（含精度/召回修正） |

## 第 7 周：适宜性模型与专家权重（尚未提交）

| 脚本 | 作用 |
|---|---|
| `week7_suitability.py` | 因子层（坡度/粗糙度/撞击坑）→ 归一化 → 加权 → 适宜性图 + 候选点排序（含 15 项自测） |
| `week7_ahp.py` | AHP 专家权重：几何平均法求权重 + 一致性比例 CR（含 11 项自测） |
| `week7_compare_literature.py` | 与论文 Fig. 5 的 4 个候选点对比：5 km 窗口评分、分位排名、距离最近的候选点（含 11 项自测，含暴力计数交叉校验） |
| `week7_finalize.sh` | 第 7 周打包：先跑全部自测，再登记产物、提交、推送，最后单向备份到 Windows |

## 第 8 周：不确定性分析（Monte Carlo）

| 脚本 | 作用 |
|---|---|
| `week8_montecarlo.py` | 200 次参数扰动（权重 Dirichlet + 阈值 + 缓冲区 + 坑目录）：逐站点排名稳定性、安全区面积分布、逐像元安全/危险概率（含 14 项自测） |
| `week8_finalize.sh` | 第 8 周打包（同上流程） |

## 测试与配置

| 文件 | 作用 |
|---|---|
| `tests/test_week5_risk.py` | 风险图数值自测 |
| `tests/test_week5_error_spatial.py` | 误差空间自测 |
| `tests/test_week6_labels.py` | 标签栅格化解析解校验（12 项） |
| `tests/test_week6_channels.py` | 输入通道/数据增强回归（17 项） |
| `tests/test_script_index.py` | **本索引的完整性检查**：被跟踪的脚本必须都出现在这里 |
| `configs/data.yaml` | 研究区、数据源参数 |
| `configs/landing_sites.csv` | 论文候选点与地标（site1/2/4 待填） |
| `configs/ahp_matrix.csv` | AHP 判断矩阵模板 |

---

## 为什么脚本名不统一

项目是边做边长的：第 1–4 周的脚本按**功能**命名（`fetch_nac.py`、`preprocess_week4.py`），
第 5 周起改成按**周次**命名（`week5_*`、`week6_*`）。改名会破坏文档链接、
历史命令和打包脚本，所以**保留原样**，改用这份索引提供导航。

## 如何使用这份索引

```bash
# 看某个脚本的完整历史（谁在什么时候加的、改过几次）
git log --oneline --follow -- scripts/fetch_nac.py

# 列出所有被跟踪的脚本
git ls-files scripts | sort

# 检查索引是否过期（应当输出 OK）
python tests/test_script_index.py
```

---

## 编辑流程：仓库是唯一真源（2026-10-02 起）

早期为了在 Windows 侧用工具编辑，脚本曾经在
`C:\Users\zwx\Documents\Codex\2026-08-14\w\scripts` 维护一份副本，
再由打包脚本复制进仓库。这个做法出过一次真实事故：**C 盘的副本比仓库新，
而实际训练用的是仓库里的旧版本**。现在方向已经倒过来：

| 角色 | 位置 | 规则 |
|---|---|---|
| **唯一真源** | `\\wsl.localhost\Ubuntu-24.04\home\zwx\projects\LunarSafeMap` | 所有编辑都在这里做 |
| **备份** | `...\w\backup_repo\`（由 `scripts/backup_to_windows.sh` 生成） | 只读，单向覆盖，用于防止磁盘故障 |
| 历史存档 | `...\w\scripts`、`...\w\docs` 等 | 第 1–6 周的旧编辑副本，保留作历史，不再更新 |

验证命令（应当输出 `ALL FILES INDEXED`）：

```bash
python tests/test_script_index.py
```
