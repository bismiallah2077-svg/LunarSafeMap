# 工作流总览

从 PDS 原始数据到"候选着陆点排名 + 不确定性区间"的完整链路。
每个方框后面括号里是负责的脚本（完整清单见 [script_index.md](script_index.md)）。

```mermaid
flowchart TD
    A["PDS / USGS 原始数据<br/>LROC NAC EDR, SLDEM2015, WAC, Robbins 目录"] --> B["ISIS 10.0.0<br/>lronac2isis / spiceinit / lronaccal / cam2map<br/>(preprocess_isis.sh, install_kernels_and_run.sh)"]
    B --> C["ASP 3.7.0 立体测图<br/>parallel_stereo + point2dem<br/>(run_nac_pair_rimae_bode.sh)"]
    C --> D["局部高分辨率 DEM<br/>3.28 m/px, 7 x 45 km 条带"]
    A --> E["研究区 DEM<br/>SLDEM 59.2 m/px, 353-359E / 8-13N<br/>(preprocess_week4.py)"]

    E --> F["多尺度地形指标<br/>坡度 / 粗糙度 / 起伏度 / 曲率<br/>(week5_terrain_metrics.py)"]
    D --> F
    F --> G["地形一致性检验<br/>NAC vs SLDEM, 误差空间结构<br/>(compare_nac_to_sldem.py, week5_error_spatial.py)"]

    A --> H["标签数据集<br/>Robbins 2018 -> 512 ppd 切片<br/>(week6_build_crater_labels.py)"]
    H --> I["U-Net 训练与消融<br/>BCE+Dice, 地理划分, 三种输入通道<br/>(week6_train_unet.py, week6_ablation.sh)"]
    I --> J["撞击坑目录<br/>连通域 -> 等效直径 -> GeoJSON<br/>(week6_mask_to_catalog.py)"]
    J --> K["人工随机抽样核查<br/>精度 0.726 / 可探测召回 0.717<br/>(week6_review_false_positives.py)"]

    F --> L["适宜性模型<br/>S = w1*H_slope + w2*H_rough + w3*H_crater<br/>(week7_suitability.py)"]
    K --> L
    L --> M["AHP 专家权重<br/>两两比较 + 一致性比例 CR<br/>(week7_ahp.py)"]
    L --> N["5 km 滑窗候选点排序<br/>candidate_sites_*.geojson"]
    M --> N
    N --> O["外部验证<br/>与论文 Fig. 5 的 LS1-LS4 对比<br/>(week7_compare_literature.py)"]

    L --> P["Monte Carlo 不确定性<br/>权重 / 阈值 / 缓冲区 / 坑目录<br/>(week8_montecarlo.py)"]
    O --> P
    P --> Q["排名稳定性 + 逐像元 P(safe)<br/>mc_sites_*.csv, mc_prob_safe_*.tif"]
    Q --> R["科研解释与讨论<br/>失败案例 / 敏感区地貌 / 局限<br/>(week9_case_studies.py, week9_discussion_CN.md)"]
```

## 数据流要点

1. **两个 DEM 分辨率**：主结果是 59.2 m/px 的 SLDEM；自产 NAC DEM（3.28 m/px）
   只覆盖研究区约 1 %（一条 7 × 45 km 条带），因此分辨率对照（H1）尚未完成。
2. **撞击坑目录是唯一"模型产出"的输入**：它的精度与召回经人工抽样核查后才有资格进入评价，
   否则误差会被误读为地形差异。
3. **阈值与权重都是假设，不是事实**：因此最终交付物是"带区间的候选点排名"，
   而不是一张单一的安全区图。
