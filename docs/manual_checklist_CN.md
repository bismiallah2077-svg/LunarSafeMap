# LunarSafeMap 人工操作清单（必须由你亲自完成的部分）

> 2026-09-18 · 配合 `docs/week4_study_area.md` 使用

项目里"能自动化"的部分已经脚本化了（下载、裁剪、清单、切片索引、底图）。
下面这些环节**必须由人来判断或操作**——不是工具不够好，而是它们要么涉及科学判断，
要么需要浏览器/眼睛，要么涉及你机器上的凭据与设备。

---

## A. 只有你能做的（不可替代）

| # | 环节 | 为什么必须人工 | 何时做 |
|---|---|---|---|
| A1 | **论文图 5 上的候选着陆点坐标** | PDF 里图 5 是图片，坐标文本提取不到；需要用眼睛读出四个点的经纬度 | 本周（10 分钟） |
| A2 | **LROC QuickMap 挑选 NAC 立体像对** | LROC 检索接口需要浏览器会话，脚本拿不到结果 | 本周（10 分钟） |
| A3 | **QGIS 视觉质检** | 判断 DEM 是否有条纹/错配、正射是否错位、WAC 与 DEM 是否对齐 | 每周成果产出后（5 分钟） |
| A4 | **撞击坑人工标注（少量真值）** | 第 6 周训练分割/检测模型需要人工标注做验证集；标注质量决定评价可信度 | 第 6 周 |
| A5 | **科学假设与参数选择** | 坡度阈值、权重方案、安全区定义——这是论文的科学论点，不是技术细节 | 第 7 周 |
| A6 | **凭据与设备** | Clash 代理开关、GitHub token、外接盘 E: 的接入/断开 | 随时 |
| A7 | **结果解释与写作** | 失败案例分析、地貌解释、局限性——这是你论文的贡献所在 | 第 9 周 |

---

## A1. 读论文图 5 的候选着陆点坐标（10 分钟）

1. 打开 `data/metadata/references/Yang2026_RimaeBode_NatureAstronomy.pdf`（若缺失，
   用仓库文档里的 DOI 重新下载）。
2. 翻到 **Fig. 5**，四个子图 (a)–(d) 分别对应 Landing site 1–4，每个子图都带经纬度轴。
3. 读出每个星的坐标（经度按**东经**记，例如 4°30'W = 355.5°E；纬度北纬为正）。
4. 填入 `configs/landing_sites.csv`，把 `site1/site2/site4` 三行的 lon/lat 补上，
   并删除该行的 `placeholder` 备注。
5. 校验：运行 `python scripts/make_study_area_map.py`，重新生成底图，
   四个星应落在研究区 353–359°E / 8–13°N 内。

参考地标（已从论文补充材料确认，可直接比对）：

| 地标 | 经度 | 纬度 |
|---|---|---|
| Bode C 撞击坑 | 355.23°E (4.77°W) | 12.22°N |
| 新鲜小撞击坑 | 355.57°E (4.43°W) | 11.46°N |

---

## A2. 挑 NAC 立体像对（10 分钟）

检索入口：<https://data.lroc.im-ldi.com/lroc/search>

**先分清两组筛选器**（表单字段已从页面源码逐项核对）：

| 字段 | 取值 | 含义 |
|---|---|---|
| Product Type | All / CDR / EDR | 数据处理级别（EDR 原始，CDR 定标后） |
| **Observation Type** | All / **NACL** / **NACR** / WAC_COLOR / WAC_MONO / WAC_UV / WAC_VIS | 相机与通道——**挑 NAC 像对要用这组** |
| West / East / South / North | 数值 | 检索范围（东经用 0–360） |
| Slew Min / Max（可勾 Absolute Value） | 数值 | 侧摆角，**这是控制交会角的关键** |
| Incidence / Emission Min / Max | 数值 | 光照与观测几何 |
| Resolution / Orbit / 日期范围 | 数值 | 其他约束 |
| Products Per Page | 10–100 | 一次列出多少条 |

**推荐检索参数**

1. 经纬度框：**开小框**，以目标点为中心，例如
   `West 354.75 / East 354.87 / South 9.82 / North 9.94`
   （约 0.12° ≈ 3.6 km 见方。框太大时命中反而少，因为需要影像覆盖整个框。）
2. Observation Type：勾 **NACL**（必要时再加 NACR）
3. Product Type：**EDR**
4. Products Per Page：100，Show Thumbnails：yes
5. 先不加 slew 限制看总数；结果少就把框再开小一点。

**找搭档的量化目标**：以 M1406995626LE（侧摆角 +16.10°）为主片，
第二景的 **Slew 应落在 −14° ~ +1°**（差值 15–30°，交会角即落入最佳区间）。
可以直接把 `Slew Min = -14`、`Slew Max = 1` 填进筛选器。

**拿不准就用校验工具**：

```bash
python scripts/stereo_check.py M1406995626LE <候选ID>
```

输出交会角、入射/出射角、分辨率与中心间距，并给出"是否可用"的结论。
## A3. QGIS 视觉质检（每周 5 分钟）

在 QGIS 里打开这几个文件，确认下面的事情：

| 文件 | 看什么 |
|---|---|
| `data/interim/week4/sldem_rimae_bode.tif` | 地形是否连续、有没有异常条纹；样式用 hillshade |
| `data/interim/week4/wac_rimae_bode.tif` | 与 DEM 叠放（透明度 50%）时影像上的坑是否对准地形上的坑 |
| `outputs/week23/dem_asp.tif` 与 `dem_difference.tif` | ASP DEM 与参考 DEM 的差异空间分布是否合理 |
| `outputs/week4/study_area_map.png` | 四个候选点是否落在研究区内 |

**判断经验**：影像和地形的坑"错半个到一个坑直径"通常是投影/中心经线设置问题；
整幅均匀偏移多为基准面（半径/大地水准面）差异——第三周那个 −264 m 就是这种。

---

## A5. 科学参数（第 7 周用，先了解）

这些参数没有"正确答案"，必须由你根据文献和试验确定，并在论文里论证：

- 坡度安全阈值（例如 10° / 15° / 20°，对应巡视器能力）
- 粗糙度窗口（3×3 / 5×5 / 11×11 与米级尺度）
- 权重方案（等权 / AHP / 熵权 / Monte Carlo 扰动）
- 撞击坑缓冲半径（按直径倍数）

---

## B. 必须理解、但可以交给脚本执行的部分

| 内容 | 为什么必须懂 |
|---|---|
| ISIS 链条 `lronac2isis → spiceinit → lronaccal → cam2map` | 出问题时只有懂流程才能定位（例如 spiceinit 需要联网内核） |
| ASP `parallel_stero → point2dem` 关键参数 | `--stereo-algorithm`、`--subpixel-mode` 直接决定精度与耗时 |
| **基准面/半径差异** | 第三周 −264 m 系统偏移的根源；跨数据集比较时必须先对齐基准 |
| **CRS 标签不可尽信** | USGS WMS 把月面经纬度标成地球 WGS84；必须自己核对 |
| PDS 标签的 `RECORD_BYTES × FILE_RECORDS` | 判断下载是否完整（清单脚本正是靠这个自动校验） |
| SHA-256 + 溯源 | 科研可复现性的底线 |

## C. 已经完全自动化（你只需跑一条命令）

```bash
python scripts/download_wac.py --bbox "353 8 359 13" --res 100   # WAC 影像
bash   scripts/download_sldem.sh <tile> data/raw/sldem2015        # SLDEM 瓦片
python scripts/preprocess_week4.py --bbox "353 8 359 13"          # DEM 裁剪
python scripts/preprocess_wac.py                                  # WAC 坐标系
python scripts/make_study_area_map.py                             # 区域底图
python scripts/build_tiles.py --tile-size 512                     # 切片索引
python scripts/build_data_manifest.py data/raw data/metadata/data_manifest.csv
```

---

## D. 新增：处理任何年份的 LROC 影像前，必须先配内核（2026-09 新增）

ISIS 自带的 LRO 内核库只覆盖到约 2019 年，**2020 年以后的 LROC 影像一律需要手动补三类内核**：

| 角色 | 文件族 | 大小参考 | 从哪找 |
|---|---|---|---|
| 轨道（SPK） | `lrorg_YYYYDDD_YYYYDDD_v01.bsp` | ~7 MB / 90 天 | `naif.jpl.nasa.gov/pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/spk/` |
| 本体姿态（CK） | `lrosc_YYYYDDD_YYYYDDD_v01.bc` | ~500 MB / 10 天 | 同上，`.../data/ck/` |
| 相机姿态（EXTRA） | `lrolc_YYYYDDD_YYYYDDD_v01.bc` | ~15 MB / 30 天 | `naif.jpl.nasa.gov/pub/naif/LRO/kernels/ck/` |

⚠️ **容易认错的三个文件族**：`lrodv` = Diviner 辐射计、`lrohg` = 高增益天线、`lrosa` = 太阳翼。
用它们会报 `ck rotation from frame -85000 can not be found`。

调用方式（`CK=` 只能给一个文件，第二个用 `EXTRA=`）：

```bash
spiceinit from=cube.cub \
  SPK="$ISISDATA/lro/kernels/spk/lrorg_YYYYDDD_YYYYDDD_v01.bsp" \
  CK="$ISISDATA/lro/kernels/ck/lrosc_YYYYDDD_YYYYDDD_v01.bc" \
  EXTRA="$ISISDATA/lro/kernels/ck/lrolc_YYYYDDD_YYYYDDD_v01.bc"
```

完整说明见 [lroc_spice_kernels.md](lroc_spice_kernels.md)。

## E. 新增：中断后如何续跑（2026-09 新增）

| 情况 | 处理 |
|---|---|
| ASP 跑到一半断电/重启 | **直接重跑同一条命令**，`parallel_stereo` 会跳过已完成的 tile |
| ISIS 步骤中断 | 脚本按"输出文件是否存在"判断，会自动跳过已完成步骤 |
| 怀疑某个 cube 写坏了 | 看文件大小是否明显偏小，删掉它再跑 |
| 电脑自动重启 | 多半是 ASP 内存打满：把脚本里 `--processes 4` 调小（8 GB 内存用 2） |

## F. 新增：第 6 周（撞击坑识别）你必须亲自做的（2026-09 新增）

机器学习部分最容易被"跑个脚本拿到数字"糊弄过去，所以这里明确列出**只有你能做、
而且必须做**的四件事。前两件各 10 分钟，后两件各 20 分钟。

### F1. 肉眼比对预测掩膜与真值掩膜（10 分钟）

```bash
# 生成一张并排对比图（左：真值圆盘，右：模型预测）
python - <<'PY'
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from osgeo import gdal
gt = gdal.Open("data/interim/week6/crater_mask_sldem.tif").ReadAsArray()
pr = gdal.Open("outputs/week6/study_area_crater_pred.tif").ReadAsArray()
f, ax = plt.subplots(1, 2, figsize=(14, 6))
ax[0].imshow(gt, cmap="gray"); ax[0].set_title("Robbins labels (truth)")
ax[1].imshow(pr, cmap="gray"); ax[1].set_title("U-Net prediction")
plt.savefig("outputs/week6/labels_vs_pred.png", dpi=130, bbox_inches="tight")
PY
```

打开 `outputs/week6/labels_vs_pred.png`（或直接拖进 QGIS）。你要回答的问题：

1. 预测出来的坑**位置**对不对？（还是整体偏移了？偏移说明配准/坐标有问题）
2. 预测的坑是**实心圆**还是**环**？环说明模型学到了坑缘（好现象）
3. 有没有把**坑链、月溪（Rimae）、坑底裂隙**误判成坑？（Rimae Bode 正好有条月溪）

### F2. 抽样核查虚警：347 个虚警里有多少是真坑（20 分钟）

```bash
# 40 个最大的虚警（大的最容易判断，也最能说明问题）
python scripts/week6_review_false_positives.py --top 40
# 只看 1-2 km 档（数量最多、最值得抽样）
python scripts/week6_review_false_positives.py --bin 1 2 --top 40
```

产出两个东西：

- `outputs/week6/review_false_positives.csv`：每个虚警的 lon / lat / 等效直径，
  **留了空的 `verdict` 和 `note` 两列给你填**；
- `outputs/week6/review_fp_map.png`：研究区 DEM 底图 + 绿圈（Robbins 真值）+ 红叉（虚警）。

在 QGIS 里把 `review_false_positives.csv` 用 "Add Delimited Text Layer" 加载
（X=lon, Y=lat），叠到 `outputs/week4/study_area_map.png` 上逐个看，然后填 `verdict`：

| `verdict` 填什么 | 含义 | 意义 |
|---|---|---|
| 确实是坑，Robbins 没收录 | a | 精度被低估 a/20 × 100% |
| 不是坑（坑链/月溪/纹理） | b | 这是真正的错误 |
| 说不清 | c | 需要更高分辨率影像（NAC）确认 |

**这一步是论文里"精度 0.451 是下界"这句话的证据**，没有它就只能靠猜。

### F3. 读懂 Robbins 目录的列（10 分钟）

```bash
head -1 data/interim/week6/robbins_raw.csv
# CRATER_ID,LAT_CIRC_IMG,LON_CIRC_IMG,LAT_ELLI_IMG,LON_ELLI_IMG,DIAM_CIRC_IMG,...
```

必须能回答：`CIRC` 是**圆形拟合**、`ELLI` 是椭圆拟合，我们用了哪一个、为什么。
（我们用 CIRC：撞击坑的**等效直径**定义来自圆，ELLI 描述的是坑缘形变。）

### F4. 判断"模型错"还是"数据不够"（20 分钟）

这是整个第 6 周最重要的一次判断。拿 1–2 km 档的漏检（221 个）做实验：

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lunarsafe
python - <<'PY'
import numpy as np
from osgeo import gdal
ds = gdal.Open("data/interim/week4/sldem_rimae_bode.tif")
print("研究区 DEM 像元: %.1f m" % (abs(ds.GetGeoTransform()[1]) * 1737400 * np.pi / 180))
print("1 km 的坑在这个分辨率下只有约 %.0f 个像元跨径" % (1000 / (abs(ds.GetGeoTransform()[1]) * 1737400 * np.pi / 180)))
PY
```

输出约 59 m/px、约 17 个像元。然后回答：**17 个像元、坑缘只占 2–3 个像元的高程变化，
信息量够判断"这是个坑"吗？** 如果不够，那漏检的瓶颈就是**数据分辨率**，
而不是模型——这正是第 3 周我们自己用 ASP 生产 3.28 m/px NAC DEM 的意义所在
（用 NAC DEM 当输入重跑同一套代码，就能把"数据不够"这个假设验证掉）。

## G. 深度学习术语速查（写论文和讨论时用）

| 英文 | 中文 | 在我们的项目里具体指什么 |
|---|---|---|
| sample / tile | 样本 / 切片 | 一块 256×256 的 DEM 窗口 |
| label / target | 标签 / 真值 | Robbins 目录坑的圆盘掩膜（1 = 坑内） |
| feature / channel | 特征 / 通道 | 高程；可选加坡度、山体阴影 |
| batch size | 批大小 | 8：一次喂 8 块切片再更新一次权重 |
| epoch | 轮 | 把训练集完整看一遍（我们 12 轮） |
| loss | 损失 | 0.5×BCE + 0.5×Dice |
| learning rate | 学习率 | 1e-3，权重每次更新的步长 |
| overfitting | 过拟合 | 训练损失降、验证损失升（我们没有出现） |
| augmentation | 数据增强 | 随机旋转 / 水平翻转 |
| IoU / P / R / F1 | 交并比 / 查准 / 查全 / F1 | 像素级：见 `metrics.csv` |
| TP / FP / FN | 真阳性 / 假阳性 / 假阴性 | 检测级：见 `catalog_metrics.csv` |
| ablation | 消融实验 | 只改一个输入通道，看分数怎么变 |
| domain shift | 域偏移 | 换光照角/换传感器后模型掉分（第 8 周要做） |
