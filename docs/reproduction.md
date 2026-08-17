# Week 3 Report: LROC NAC Stereo DEM and First Error Analysis

> 复现文档 · LunarSafeMap · 2026-08-17

## 1. 目标

1. 从 PDS 原始数据出发，完成 LROC NAC 立体像对的 ISIS 全流程（导入 → 几何初始化 → 辐射标定 → 裁剪 → 地图投影）；
2. 用 ASP 生成 DEM、正射影像与三角测量误差图；
3. 与参考 DEM（LDEM_128，128 ppd ≈ 236 m/px）做首次高程误差分析。

## 2. 数据与环境

| 项目 | 值 |
|---|---|
| 立体像对 | M181058717LE / M181073012LE（LROC NAC，2012-01-13） |
| 区域 | 15.21–15.40°E，7.98–9.67°S |
| 原始数据 | PDS3 EDR（各 264 MB，内嵌标签），来源见 `data/metadata/data_manifest.csv` |
| 软件 | ASP 3.7.0 + ISIS 10.0.0 + GDAL 3.12（WSL2 Ubuntu 24.04） |
| 参考 DEM | LDEM_128（LOLA，128 ppd，约 236 m/px） |

## 3. 处理流程

```text
EDR (.IMG)
  └─ lronac2isis   → ISIS cube（格式转换）
     └─ spiceinit  → SPICE 内核（星历/指向/时钟/形状模型）
        └─ lronaccal → 辐射标定（暗电流、平场）
           └─ crop   → 重叠区裁剪（900×973 / 1173×1218）
              ├─ cam2map → 地图投影标准影像（SimpleCylindrical, 4 m/px）
              └─ parallel_stereo → 点云
                 └─ point2dem → DEM / 正射 / 三角误差图
                    └─ 与 LDEM_128 比较 → 误差统计 + 协变量分析
```

一键复现：

```bash
cd ~/projects/LunarSafeMap
bash scripts/run_week2_3.sh
```

## 4. 结果

### 4.1 DEM 误差统计（ASP − LDEM_128）

| 统计量 | 原始值 | 去偏后（减中位数） |
|---|---:|---:|
| n | 47409 | 47409 |
| mean | −263.6 m | ~0 |
| RMSE | 264.6 m | ≈ 23 m |
| median | −266.2 m | — |
| p1 / p99 | −303.4 / −217.5 m | — |

**解读**：误差以几乎恒定的 −264 m 系统偏移为主，离散仅约 23 m。这是**垂直基准不一致**（ASP 输出相对其参考面，LDEM 相对 1737400 m 平均半径球）造成的系统偏差，不是匹配失败。去偏后的 ~23 m 残差包含：参考 DEM 分辨率（236 m）与 ASP DEM（4 m）的差异、少量水平配准误差、以及真实的亚像元地形细节。

### 4.2 误差与协变量（原始偏差分箱）

| 协变量 | 分箱 | RMSE 范围 |
|---|---|---|
| 坡度 | 0.85°–90° | 261.6 → 272.8 m |
| 亮度 | 0.15–1.18 | 254.7 → 275.1 m |
| 纹理 | 0–0.30 | 267.9 → 259.4 m |

坡度越高误差略增（约 12 m），提示存在轻微的水平错位在坡地上的投影；但相对系统偏移仍为次要量级。

## 5. 局限与下一步

1. **配准**：用 `pc_align` 估计水平 + 垂直偏移，验证 −264 m 是否为纯垂直平移；
2. **参考对比**：改用 SLDEM2015 或该像对官方 NAC DTM（4–8 m 级）做第二组比较，把"参考分辨率贡献"分离出来；
3. **分辨率实验**：重跑 `point2dem --tr`（4/8/20 m）与 `cam2map` 分辨率，量化 H1 分辨率效应；
4. **匹配算法**：对比 `asp_mgm` 与 `asp_bm`、`--subpixel-mode 2`，评估算法与亚像素精度的影响。

## 6. 已知环境说明

- 本地 SPICE 内核的 ck 指向存在覆盖问题，`spiceinit` 当前使用 `web=yes`（联网模式）初始化；结果与本地模式等价；
- 大数据（原始影像、cube、DEM）不入库，复现所需下载说明见 `data/metadata/data_manifest.csv`。
