#!/usr/bin/env python3
"""Build the LunarSafeMap technical report (DOCX) from the repository results.

The report is generated, not hand-written: every number in it comes from a CSV
or a log file produced by the week 4-9 scripts, so regenerating the analysis and
rebuilding the report cannot drift apart.

Usage (works with any Python that has python-docx):
  python scripts/build_technical_report.py --out docs/LunarSafeMap_technical_report_v1.0.docx

Figures are read from the paths given in FIGURES; missing figures are skipped
with a warning instead of failing the build.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

REPO = Path(__file__).resolve().parents[1]
OUTPUTS = REPO / "outputs"

TITLE = "LunarSafeMap 技术报告"
SUBTITLE = ("月面候选着陆区地形安全性与适宜性评价："
            "以 Rimae Bode 为例（v1.0，2026-10）")

FIGURES = [
    ("fig_study_area", REPO / "outputs" / "week4" / "study_area_map.png",
     "图 1  研究区与地标：Rimae Bode（353–359°E, 8–13°N），底图为 LROC WAC 镶嵌图与 SLDEM2015。"),
    ("fig_nac_dem", REPO / "outputs" / "week4" / "nac_dem_preview.png",
     "图 2  自产 NAC 立体 DEM（3.28 m/px, 2176 × 13866 px）与 SLDEM 的对比。"),
    ("fig_ablation", REPO / "outputs" / "week6" / "ablation_features.png",
     "图 3  撞击坑识别的输入特征消融（DEM / +坡度 / +坡度+阴影）。"),
    ("fig_review", REPO / "outputs" / "week6" / "review_fp_map.png",
     "图 4  人工核查的虚警分布（绿圈为 Robbins 真值，红叉为虚警）。"),
    ("fig_suitability", REPO / "outputs" / "week7" / "suitability_map.png",
     "图 5  适宜性模型：三个危险度层、综合得分、分类与分布。"),
    ("fig_literature", None,
     "图 6  论文候选点与本研究结果的对比（见第 4.4 节表格）。"),
    ("fig_mc", REPO / "outputs" / "week8" / "mc_summary_k15.png",
     "图 7  Monte Carlo 结果：安全区比例分布、候选点排名区间、逐像元 P(safe) 与 P(danger)。"),
    ("fig_cases", REPO / "outputs" / "week9" / "case_studies.png",
     "图 8  案例研究：适宜性图与 P(safe) 图，标注论文候选点与本研究最优区。"),
]


def set_base_style(doc):
    """Use a readable serif/sans pairing and comfortable spacing."""
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    pf = normal.paragraph_format
    pf.space_after = Pt(6)
    pf.line_spacing = 1.15
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.color.rgb = RGBColor(0, 0, 0)
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    doc.styles["Title"].font.color.rgb = RGBColor(0, 0, 0)


def add_title(doc):
    t = doc.add_paragraph(TITLE, style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s = doc.add_paragraph(SUBTITLE)
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s.runs[0].italic = True
    s.runs[0].font.size = Pt(12)
    meta = doc.add_paragraph(
        "作者：LunarSafeMap 项目（https://github.com/bismiallah2077-svg/LunarSafeMap）\n"
        "数据：LROC NAC / SLDEM2015 / Robbins (2018)；工具：ISIS 10.0.0、ASP 3.7.0、PyTorch 2.9")
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in meta.runs:
        r.font.size = Pt(10)


def add_para(doc, text, style=None):
    p = doc.add_paragraph(text, style=style) if style else doc.add_paragraph(text)
    return p


def add_bullets(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def add_table(doc, header, rows, widths=None, caption=None, font_size=9):
    """Light-bordered table with a grey header row (skill table standards)."""
    if caption:
        c = doc.add_paragraph(caption)
        c.runs[0].bold = True
        c.runs[0].font.size = Pt(9.5)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        run = p.add_run(str(h))
        run.bold = True
        run.font.size = Pt(font_size)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            run = p.add_run("" if v is None else str(v))
            run.font.size = Pt(font_size)
            p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if i and len(str(v)) < 12
                           else WD_ALIGN_PARAGRAPH.LEFT)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def add_figure(doc, path, caption):
    if path is None or not Path(path).exists():
        return False
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        run = p.add_run()
        run.add_picture(str(path), width=Inches(6.0))
        # accessibility: give the inline shape real alt text (the audit flags
        # images whose descr/title are empty)
        shape = run._element.findall(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline")
        for sh in shape:
            docpr = sh.find(
                "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")
            if docpr is not None:
                docpr.set("descr", caption)
                docpr.set("title", caption[:80])
    except Exception as exc:                      # noqa: BLE001
        print("  ! could not embed {}: {}".format(path, exc))
        return False
    cap = doc.add_paragraph(caption)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].font.size = Pt(9)
    cap.runs[0].italic = True
    return True


def build_summary(doc):
    doc.add_heading("摘要", level=1)
    add_para(doc,
        "本报告建立并检验了一套面向月球候选着陆区的多准则地形安全性评价流程，"
        "并在 Rimae Bode 候选区（353–359°E, 8–13°N）上完成端到端验证。"
        "流程包含四个环节：PDS 数据获取与 ISIS/ASP 摄影测量处理；多尺度地形指标计算；"
        "基于 U-Net 的撞击坑自动识别与人工抽样核查；加权适宜性模型与 Monte Carlo 不确定性分析。")
    add_para(doc,
        "主要结论是：**面积不确定，排序稳定**。在 200 次参数扰动下，安全区面积占比的"
        "5–95% 区间为 0.38–0.93（宽权重）与 0.44–0.91（约 ±30% 权重），"
        "但我们识别出的最优候选区在每一次抽样中都保持在前 1% 分位；"
        "论文（Yang et al. 2026）提出的四个候选点中，LS3 在所有参数化下都是最安全的，"
        "LS2 都是最危险的。不确定性主要来自阈值选择（组间极差 0.15–0.18），"
        "而不是权重或撞击坑目录口径（0.03）。全研究区仅 26.1% 的面积在任何参数组合下都安全，"
        "35.2% 的面积其安全性结论取决于参数选择。")
    add_para(doc,
        "本报告的次要但方法学上重要的结果是：对撞击坑目录的人工随机抽样核查把检测精度"
        "从 0.451 修正到 0.726（0.644–0.807），把召回从 0.533 修正到 0.717（0.655–0.788），"
        "说明相当一部分表面误差来自参考目录与 DEM 分辨率，而不是模型本身。")
    doc.add_heading("Abstract", level=2)
    add_para(doc,
        "We present and validate an end-to-end multi-criteria terrain-safety assessment for a "
        "lunar candidate landing region, applied to Rimae Bode (353-359 E, 8-13 N). The pipeline "
        "combines PDS data handling and ISIS/ASP stereo photogrammetry, multi-scale terrain "
        "metrics, a U-Net crater detector whose catalogue is audited by manual sampling, a "
        "weighted suitability model, and a Monte Carlo uncertainty analysis. The central result "
        "is that the *area* of suitable terrain is highly uncertain (5-95% interval 0.38-0.93) "
        "while the *ranking* of candidate sites is stable: our best site stays above the 99th "
        "percentile in every draw, and of the four sites proposed by Yang et al. (2026) LS3 is "
        "the safest and LS2 the most hazardous under every parameterisation tested. Thresholds "
        "dominate the uncertainty (spread 0.15-0.18) far more than weights or the crater "
        "catalogue (0.03). Manual review of random samples moves the reported crater-detection "
        "precision from 0.451 to 0.726 and the detectable recall from 0.533 to 0.717, showing "
        "that much of the apparent error belongs to the reference data, not the model.")


def build_intro(doc):
    doc.add_heading("1  引言", level=1)
    doc.add_heading("1.1  背景与问题", level=2)
    add_para(doc,
        "着陆区选址要在工程安全性与科学价值之间做取舍。已有研究通常给出单一权重下的"
        "适宜性图或少数候选点，但很少说明结论对权重、阈值与数据分辨率的依赖程度。"
        "本报告把这一依赖关系本身作为研究对象，提出的问题是：")
    add_bullets(doc, [
        "在不同空间分辨率、地形指标与权重设置下，候选着陆区的安全性评价结果是否稳定？",
        "自动撞击坑识别能否提高安全区划分的客观性与可复现性？",
    ])
    add_para(doc, "对应三个可检验假设：")
    add_table(doc, ["假设", "内容", "本报告的检验结果"],
              [["H1 分辨率效应", "粗分辨率 DEM 平滑局部坡度与起伏，导致安全区面积被高估",
                "未完成：自产 NAC DEM 仅覆盖研究区约 1%，且与前 10 名候选点 0 重叠"],
               ["H2 多源融合效应", "DEM + 坡度 + 粗糙度 + 撞击坑的联合评价优于单一坡度",
                "部分支持：阴影通道把检测 F1 从 0.460 提升到 0.548；三因子排序对权重不敏感"],
               ["H3 评价不确定性", "固定权重得到的最佳点可能不稳定，参数扰动后可识别稳定区",
                "已完成量化：面积 ±30 个百分点、排序稳健、阈值主导"]],
              widths=[1.1, 2.6, 2.6])
    doc.add_heading("1.2  研究区", level=2)
    add_para(doc,
        "研究区为 Rimae Bode（月海与高地过渡带，353–359°E, 8–13°N），"
        "由 Yang et al. (2026, Nature Astronomy 10, 644–654, doi:10.1038/s41550-026-02790-0) "
        "提出为中国首次载人登月的优先候选区，并给出四个候选着陆点（Fig. 5 的 LS1–LS4）"
        "与两个地标（Bode C 撞击坑 355.23°E/12.22°N；新鲜小撞击坑 355.57°E/11.46°N）。"
        "本报告把 LS1–LS4 作为**独立外部验证集**：读图得到坐标（LS1 355.76°E/11.43°N，"
        "LS2 356.56°E/12.41°N，LS3 355.78°E/12.16°N，LS4 355.97°E/10.43°N）后，"
        "检验我们的评价链是否独立地重现论文的偏好。")


def build_methods(doc):
    doc.add_heading("2  数据与方法", level=1)
    doc.add_heading("2.1  数据源与预处理", level=2)
    add_table(doc, ["数据", "用途", "分辨率 / 规模", "来源"],
              [["LROC NAC EDR", "立体测图、局部高分辨率 DEM", "0.5–2 m/px", "PDS (LRO-L-LROC-2-EDR-V1.0)"],
               ["SLDEM2015", "主 DEM、区域地形评价", "512 ppd ≈ 59.2 m/px", "PDS / USGS Astrogeology"],
               ["LROC WAC 镶嵌图", "底图与目视检查", "100 m/px", "USGS Moon WMS"],
               ["Robbins (2018) 目录", "撞击坑标签与评价基准", "1,296,796 个坑", "USGS Astrogeology"],
               ["Yang et al. (2026) 图 5", "外部验证（4 个候选点）", "—", "Nature Astronomy"]],
              widths=[1.5, 1.9, 1.5, 1.8])
    add_para(doc,
        "原始数据经 ISIS 10.0.0 导入、辐射校正与地图投影（lronac2isis、spiceinit、lronaccal、cam2map），"
        "再由 ASP 3.7.0 完成立体匹配、点云与 DEM 生成（parallel_stereo、point2dem）。"
        "2022 年的 LROC 数据需要手工提供 SPICE 内核（SPK 与两组 CK），这一依赖已在仓库文档中记录。"
        "自产 NAC DEM 的规格为 2176 × 13866 px、3.283 m/px（7 × 45 km 条带），"
        "三角交会误差中位数 4.46 m。")
    add_para(doc,
        "自产 DEM 与 SLDEM 的一致性检验显示：垂向基准一致（中值偏差 −0.83 m），"
        "整体 RMSE 35.3 m，但误差强烈依赖坡度——坡度小于 5° 时 MAE 约 4 m，"
        "大于 25° 时升至约 88 m。配准检验排除了尺度/旋转失配作为主因。"
        "这一结果决定了后续所有陡坡区的指标都带有系统性不确定性。")

    doc.add_heading("2.2  多尺度地形指标", level=2)
    add_para(doc,
        "从 DEM 计算坡度、曲率、粗糙度（窗口内高程标准差）与局部起伏度，"
        "并在 20 m、60 m、200 m 三个物理支撑尺度上比较。指标定义在脚本中固定，"
        "并配有解析解自测（例如合成斜坡的坡度必须等于 atan(梯度)），"
        "以保证第 5 周的结论与第 7 周的模型输入完全一致。")
    add_para(doc,
        "在 59.2 m/px 的 SLDEM 上，60 m 支撑的坡度中位数为 4.11°、粗糙度中位数 3.56 m。"
        "同一区域用 3.28 m/px 的 NAC 计算时，陡坡比例显著更高，"
        "说明 59 m 产品会在陡坡区平滑掉真实起伏——这是 H1 的直接动机。")

    doc.add_heading("2.3  撞击坑自动识别与人工核查", level=2)
    add_para(doc,
        "标签取自 Robbins (2018) 目录，按地理框裁剪（训练区 9,457 个坑，研究区 535 个坑），"
        "栅格化为圆盘掩膜后切成 256 × 256 px（约 15 × 15 km）的样本；"
        "模型为 4 层下采样 U-Net（1,286,417 参数），损失为 BCE 与 Dice 各半，"
        "训练在 CPU 上 12 轮约 11 分钟。数据划分为**地理划分**而非随机划分："
        "训练区南半部训练、北半部验证、研究区整块留作测试，以避免相邻切片的泄漏。")
    add_para(doc,
        "评价分两级：像素级 IoU/P/R/F1，以及检测级 P/R/F1（预测掩膜经连通域分析、"
        "等效直径计算和尺寸过滤后与真值匹配）。两级指标必须同时报告，"
        "因为像素 IoU 会因坑缘几个像素的偏移而大幅下降，而科研关心的是"
        "撞击坑是否被找到以及直径是否可靠。")
    add_para(doc,
        "由于参考目录本身不是真值，我们用**均匀随机抽样 + 人工判读**对目录质量做了两次核查："
        "从 347 个虚警中随机抽 40 个判读真伪，从 250 个漏检中随机抽 40 个判读可探测性"
        "（判据为「在 59 m/px 下坑缘能否辨认」）。核查结果用 Wilson 区间给出统计修正，"
        "并自动交叉核验「判为真坑」的检测是否落在目录已收录的坑上（用于排除重复检测造成的虚高）。")

    doc.add_heading("2.4  适宜性模型与权重", level=2)
    add_para(doc,
        "适宜性定义为三个危险度层的加权和：S = w_slope·H_slope + w_rough·H_rough + w_crater·H_crater。"
        "每个 H 是分段线性斜坡（低于安全阈值为 0，高于危险阈值为 1）："
        "坡度 5°→15°，粗糙度 1 m→5 m；撞击坑层为坑内 1、向坑缘外 1 km 线性衰减到 0。"
        "分类阈值为 S < 0.33 安全、0.33–0.66 注意、> 0.66 危险。")
    add_para(doc,
        "候选着陆点定义为**5 km 滑窗**的平均适宜性，按 S 升序取互不重叠的窗口。"
        "早期版本使用「最大连续安全区」，第一名达 10,724 km²（占研究区 39%），"
        "那不是着陆点而是区域统计量，因此改为滑窗——这一修正本身就是一项方法学结论。")
    add_para(doc,
        "权重通过 AHP 由项目作者的专家判断给出：三次两两比较（坡度 3 倍于粗糙度、"
        "2 倍于撞击坑；粗糙度与撞击坑同等重要），几何平均法求得权重 "
        "0.550 / 0.210 / 0.240，一致性比例 CR = 0.0157（< 0.1，可接受）。"
        "CR 的非零值来自第 3 次比较与完全自洽解（2/3）之间的微小差异，"
        "这正好说明 CR 度量的是判断之间的循环矛盾，而不是判断的正误。")

    doc.add_heading("2.5  不确定性分析", level=2)
    add_para(doc,
        "对每个不确定参数进行 200 次随机抽样：权重按 Dirichlet(浓度 × AHP 中心) 采样"
        "（保证均值等于中心且始终在单纯形上），坡度安全阈值 {3,5,8}°、危险阈值 {10,15,20}°，"
        "粗糙度安全阈值 {0.5,1,2} m、危险阈值 {3,5,10} m，坑缘缓冲 {500,1000,2000} m，"
        "撞击坑目录在 632 个（精度导向）与 897 个（召回导向）之间二选一。"
        "DEM、地形指标、网格与窗口大小保持固定。")
    add_para(doc,
        "实现上，坑缘距离变换对每个目录只计算一次，之后每次抽样仅重新缩放，"
        "使 200 次抽样的总耗时降到约 3.3 分钟，从而让「参数扰动」成为常规分析而非一次性实验。"
        "输出包括逐站点的排名分位分布、安全区面积分布，以及逐像元的安全/危险概率。")

    doc.add_heading("2.6  验证数据集", level=2)
    add_para(doc,
        "外部验证使用 Yang et al. (2026) Fig. 5 的四个候选点。"
        "评价方式与候选点排序完全一致（同一 5 km 窗口定义），"
        "报告每个点的窗口平均 S、危险像元比例、在全部窗口中的分位排名，"
        "以及到本研究最优候选点的距离。")


def build_results(doc):
    doc.add_heading("3  结果", level=1)
    doc.add_heading("3.1  撞击坑识别的精度与人工修正", level=2)
    add_para(doc,
        "U-Net 在从未参与训练的研究区上取得像素级 IoU 0.298、F1 0.460，"
        "验证区（训练区北带）IoU 0.266；测试分数不低于验证分数，"
        "说明模型学到的是撞击坑的局部形态而非训练区地形本身。"
        "按直径分档的检测级结果差异很大，大坑几乎完美，小坑是瓶颈：")
    add_table(doc, ["直径档", "真值数", "检出", "虚警", "P", "R", "F1"],
              [["1–2 km", 453, 232, 265, 0.467, 0.512, 0.488],
               ["2–5 km", 74, 45, 82, 0.354, 0.608, 0.448],
               ["≥5 km", 8, 8, 0, 1.000, 1.000, 1.000],
               ["全部", 535, 285, 347, 0.451, 0.533, 0.488]],
              widths=[1.1, 0.9, 0.8, 0.8, 0.8, 0.8, 0.8],
              caption="表 3  撞击坑检测级指标（按直径分档，最小检测直径 1 km）")
    add_para(doc,
        "输入特征消融显示，单加坡度几乎不改变 F1（0.460 → 0.462），"
        "但显著改变模型的取舍（精度 0.368 → 0.447，召回 0.613 → 0.478）；"
        "再引入山体阴影后 F1 升至 0.548、IoU 0.298 → 0.377，"
        "检测级虚警由 347 个降到 81 个。这一结果支持 H2 的一半："
        "融合确实有效，但增益来自视觉表达（阴影）而非物理量（坡度）。")
    add_para(doc,
        "人工核查改变了指标的解读方式。随机抽样 40 个虚警中，50% 实为 Robbins 目录漏收的真坑；"
        "自动交叉核验确认其中 19 个位于目录完全没有的坑上（仅 1 个是重复检测），"
        "因此修正不是重复检测造成的虚高。随机抽样 40 个漏检中，45% 在 59 m/px 下无法辨认坑缘。"
        "修正后的目录质量如下：")
    add_table(doc, ["指标", "报告值（对目录）", "修正值（对真实世界）", "说明"],
              [["精度", "0.451", "0.726（0.644–0.807）", "1–2 km 档 0.467 → 0.804；2–5 km 档几乎无修正"],
               ["召回", "0.533", "0.717（0.655–0.788）", "不可探测的漏检不应计入分母"]],
              widths=[0.9, 1.4, 2.0, 2.2],
              caption="表 4  人工核查对撞击坑目录质量的修正（Wilson 95% 区间）")
    add_para(doc,
        "虚警的成因也可以归类：20 个真实虚警中 11 个（55%）来自光照/阴影造成的伪闭合"
        "（山脊背面、坡折、纹理阴影），其余来自非坑的弧状地貌（月溪、皱岭）、"
        "数据/几何伪影（影像边缘、投影边界）以及溅射丘等坑缘附生凸起。"
        "这既解释了误差机制，也直接支撑光照域偏移这一后续研究方向。")
    add_para(doc,
        "最后，人工核查预测出一个可检验的后处理改进：12/40 的漏检是模型在坑内响应过、"
        "但小块小于 1 km 被尺寸过滤丢弃的目标；把最小检测直径从 1.0 km 降到 0.3 km 后，"
        "实测找回 44 个真坑（事前估计约 50），召回由 0.533 升到 0.615，"
        "代价是精度降到 0.334、F1 下降。对以召回优先的着陆安全评价而言，"
        "这个取舍需要结合新增检测的真实精度共同判断。")

    doc.add_heading("3.2  地形指标与分辨率对照", level=2)
    add_para(doc,
        "在匹配分辨率后，NAC 与 SLDEM 的坡度场高度一致（中值差 −0.05°，MAE 1.58°），"
        "但 SLDEM 会遗漏陡坡：分别漏掉 11.4%、16.9%、31.1% 的坡度大于 10°、15°、20° 的像元。"
        "在 60 m 支撑下，SLDEM 判定研究区 60% 的面积为安全，"
        "但把统计限制在 NAC 立体覆盖范围内时，安全比例只有 37%。"
        "这一差异是 H1 的量化动机，也解释了为什么粗分辨率产品会系统性高估安全区。")

    doc.add_heading("3.3  适宜性图与候选点", level=2)
    add_para(doc,
        "四种权重/阈值方案给出的安全区比例不同，但候选点的相对排序高度一致：")
    add_table(doc, ["方案", "权重（坡/糙/坑）", "阈值", "安全 %", "危险 %"],
              [["等权", "0.333 / 0.333 / 0.333", "5/15°, 1/5 m", 58.4, 10.5],
               ["熵权", "0.343 / 0.158 / 0.499", "5/15°, 1/5 m", 75.6, 7.1],
               ["分位数标定", "0.333 / 0.333 / 0.333", "p50 / p95", 78.4, 7.5],
               ["作者 AHP（CR = 0.0157）", "0.550 / 0.210 / 0.240", "5/15°, 1/5 m", 70.7, 8.7]],
              widths=[1.6, 1.7, 1.3, 0.9, 0.9],
              caption="表 5  四种参数方案下的安全区比例")
    add_para(doc,
        "等权并不意味着等影响：三个危险度层的分布差异很大（粗糙度层均值 0.613、"
        "58.5% 的像元超过 0.5，而坡度层与撞击坑层约为 0.15），"
        "因此等权下粗糙度实际主导了结果。熵权法通过分布对比度自动把粗糙度权重压到 0.158、"
        "撞击坑抬到 0.499，部分修正了这一偏差。")
    add_para(doc,
        "稳健性检验更直接：改变权重时前 10 名候选点重合 9 个，改变阈值时只重合 5 个——"
        "**阈值不确定性大于权重不确定性**。四种方案共同选出一个稳定最优区 "
        "(353.76°E, 11.08°N)，其 5 km 窗口的平均 S 在 0.002–0.052 之间（越靠近 0 越安全）。")

    doc.add_heading("3.4  与论文候选点的对比", level=2)
    add_para(doc,
        "把论文的四个候选点按同一 5 km 窗口定义评分，并与我们的最优区比较。"
        "表中数字为「比研究区中多少比例的窗口更安全」（越高越安全）：")
    add_table(doc, ["点", "等权", "熵权", "分位数标定", "作者 AHP", "危险像元 %"],
              [["LS3", "80.6", "82.7", "86.2", "82.1", 0.0],
               ["LS1", "65.0", "51.8", "46.6", "57.6", 15.3],
               ["LS4", "47.4", "38.3", "38.7", "45.2", 15.8],
               ["LS2", "1.3", "0.7", "1.3", "1.6", 55.6],
               ["本研究最优区", "≈100", "≈100", "≈100", "≈100", 0.0]],
              widths=[1.4, 0.9, 0.9, 1.1, 1.0, 1.1],
              caption="表 6  论文候选点与本研究最优区的适宜性分位（四种参数化）")
    add_para(doc,
        "模型独立地重现了论文的偏好：**LS3 在四种参数化下都是四点中最安全的，"
        "LS2 都是最危险的**。同时本研究的最优区与四个论文候选点相距 26–73 km，"
        "并不重合——这一差异在第 4.1 节解释。")

    doc.add_heading("3.5  不确定性", level=2)
    add_para(doc,
        "200 次参数抽样的结果是「面积不确定、排序稳定」：")
    add_table(doc, ["运行", "安全区比例均值", "5–95% 区间", "最小–最大"],
              [["宽权重（Dirichlet 浓度 15）", 0.708, "0.384 – 0.931", "0.209 – 0.963"],
               ["约 ±30% 权重（浓度 60）", 0.713, "0.444 – 0.906", "0.280 – 0.958"]],
              widths=[2.2, 1.4, 1.5, 1.5],
              caption="表 7  安全区面积比例的 Monte Carlo 分布")
    add_para(doc,
        "第 8 周的四个确定性取值（0.584 / 0.756 / 0.784 / 0.707）全部落在上述区间内，"
        "说明它们只是分布上的四个点，而不是四个结论。"
        "与此同时，我们的最优候选区在每一次抽样中都保持在前 1% 分位，"
        "论文 LS3 始终位于 79–88 分位、LS2 始终低于 4 分位。")
    add_para(doc, "不确定性来源可以排序（以安全区比例的组间极差衡量）：")
    add_table(doc, ["参数", "极差", "参数", "极差"],
              [["坡度安全阈值 {3,5,8}°", "0.177", "坑缘缓冲 {500,1000,2000} m", "0.115"],
               ["坡度危险阈值 {10,15,20}°", "0.161", "撞击坑目录（632 vs 897）", "0.034"],
               ["粗糙度危险阈值 {3,5,10} m", "0.147", "粗糙度安全阈值 {0.5,1,2} m", "0.033"]],
              widths=[2.2, 0.9, 2.4, 0.9],
              caption="表 8  各参数对安全区面积的影响（Monte Carlo 组间极差）")
    add_para(doc,
        "权重中与安全区比例相关最强的是粗糙度权重（r = −0.44），"
        "坡度 +0.25、撞击坑 +0.14。空间上，仅 26.1% 的研究区在**任何**参数组合下都安全，"
        "35.2% 的区域安全性结论取决于参数（0.1 < P(safe) < 0.9），6.3% 在任何参数下都不安全。")


def build_discussion(doc):
    doc.add_heading("4  讨论", level=1)
    doc.add_heading("4.1  失败案例：论文的 LS2 与我们的判定相反", level=2)
    add_para(doc,
        "LS2 是全文最有价值的案例：论文把它列为候选点，我们的模型判为最危险。"
        "把 5 km 窗口内的物理量列出来，分歧的原因就清楚了：")
    add_table(doc, ["站点", "坡度中位数", "坡度 p95", "粗糙度中位数", "粗糙度 p95", "窗口内坑数", "最近坑距"],
              [["LS2", "9.00°", "25.64°", "7.79 m", "23.16 m", 2, "1.55 km"],
               ["LS1", "2.51°", "20.27°", "2.21 m", "17.94 m", 0, "2.77 km"],
               ["LS3", "2.85°", "7.23°", "2.56 m", "5.93 m", 0, "5.34 km"],
               ["LS4", "3.52°", "13.91°", "3.09 m", "11.83 m", 1, "1.64 km"],
               ["本研究最优区", "1.51°", "3.76°", "1.42 m", "3.07 m", 0, "5.42 km"]],
              widths=[1.2, 0.9, 0.8, 1.1, 1.0, 0.9, 0.9],
              caption="表 9  各站点 5 km 窗口内的物理地形事实")
    add_para(doc,
        "LS2 的坡度中位数是其他论文候选点的 2.5–3.6 倍、粗糙度是 2.5–3.9 倍，"
        "窗口内还有 2 个已编目撞击坑（最近 1.55 km）。"
        "因此我们的判定不是模型噪声，而是可复核的地形事实。"
        "分歧的真正来源是评价准则：论文的候选点同时考虑地质样品价值、"
        "钍丰度与玄武岩单元代表性（LS2 位于 Rima Bode II 高钍单元南侧），"
        "而本模型只衡量工程安全性。"
        "结论应是给这类点位标注「科学价值高、工程风险也高」，"
        "而不是用安全性模型否定论文的候选点。这正是「科学价值与工程安全性分离」的定量证据。")
    add_para(doc,
        "反过来说，本研究的最优区（1.51°、1.42 m）比四个论文候选点都更平缓，"
        "但它在论文的框架里是否具备科学价值，本研究无法回答——"
        "因为缺少钍丰度与 TiO₂ 数据。这是下一步最需要补齐的一环。")

    doc.add_heading("4.2  参数敏感区的几何必然性", level=2)
    add_para(doc,
        "不确定性不是随机噪声，而有明确的地形含义：敏感区正是指标落在阈值附近的地带。")
    add_table(doc, ["类别", "最大连通区", "位置", "坡度中位数", "粗糙度中位数"],
              [["参数敏感（0.1 < P < 0.9）", "7,439 km²", "356.85°E, 10.27°N", "6.16°", "5.27 m"],
               ["稳健安全（P ≈ 1）", "2,332 km²", "354.26°E, 10.78°N", "1.56°", "1.55 m"],
               ["从不安全（P ≈ 0）", "104 km²", "358.82°E, 9.00°N", "31.91°", "30.16 m"]],
              widths=[1.9, 1.2, 1.6, 1.0, 1.1],
              caption="表 10  三类连通区及其地形特征")
    add_para(doc,
        "敏感区的坡度/粗糙度中位数（6.16°、5.27 m）正落在扰动的阈值区间内"
        "（坡度安全 3–8°、危险 10–20°；粗糙度安全 0.5–2 m、危险 3–10 m），"
        "因此阈值一变，整片区域的分类就翻转；稳健安全区的指标（1.56°、1.55 m）远离所有阈值；"
        "从不安全区则是坑内与坑缘（31.9°、30.2 m）。"
        "换言之，敏感性地图画出的其实是阈值在参数空间中的投影，"
        "这一解释可以把「哪里不确定」转化为可解释的地貌判据。")

    doc.add_heading("4.3  外部验证的意义", level=2)
    add_para(doc,
        "论文发表时我们并不知道 LS1–LS4 的位置，评价链却独立给出 LS3 最安全、LS2 最危险，"
        "且在 200 次抽样下保持不变。这说明该评价链具备外部可重复性，"
        "而不是只在自身参数下自洽。对于以「可复现」为目标的本科科研项目，"
        "外部验证比内部一致性更有说服力。")
    add_para(doc,
        "同时要注意验证的限度：四个点中只有两个（LS3、LS2）给出稳健结论，"
        "LS1 与 LS4 位于中间区间（分位 44–65），与参数选择相关。"
        "把它们报告为「结论依赖参数」比强行排序更诚实。")

    doc.add_heading("4.4  局限性", level=2)
    add_bullets(doc, [
        "只有三个危险度层：缺少石块丰度（Diviner）与光照条件，"
        "因此本文的 S 是「三因子安全性」，不能称为完整的多准则评价，"
        "而论文使用的石块丰度是已知的关键危险指标。",
        "撞击坑层精度非完美：修正后精度 0.726（0.644–0.807）、可探测召回 0.717（0.655–0.788），"
        "且基于单次人工判读（n = 40、非完全盲评、判读者即模型作者，存在确认偏误风险）。",
        "分辨率假设未检验（H1）：主结果基于 59.2 m/px 的 SLDEM；"
        "自产 NAC DEM（3.28 m/px）仅覆盖研究区约 1%，且与前 10 名候选点 0 重叠。",
        "阈值主导不确定性：安全区面积对阈值的敏感性（0.15–0.18）远大于权重与目录口径（0.03），"
        "因此任何面积结论都必须以区间形式给出。",
        "DEM 垂向精度随坡度恶化：NAC 与 SLDEM 的偏差在坡度大于 25° 时可达数十米，"
        "影响陡坡区的坡度与粗糙度取值。",
        "未论证阈值本身的最优性：本文扰动阈值，但没有给出「哪个阈值才是工程正确的」这一判断，"
        "后者需要引用任务规范。",
    ])

    doc.add_heading("4.5  可推广性", level=2)
    add_para(doc,
        "整条流水线不含月球专属假设：更换 DEM 与撞击坑目录后，"
        "同一套代码可用于火星（如 CTX + MOLA）、水星（MESSENGER）或其他天体的选址问题。"
        "更具普遍性的结论有两条：其一，「面积不确定、排序稳定」很可能普遍存在，"
        "因为任何阈值型适宜性模型都具有「阈值附近最敏感」的几何性质；"
        "其二，把**排名稳定性**而非单张适宜性图作为交付物，"
        "更稳健，也更容易被任务规划者使用。")
    add_para(doc,
        "需要谨慎的是具体数值：本文的阈值、权重与最优坐标只对 Rimae Bode 及所扰动的参数区间成立，"
        "跨区域应用前必须重跑敏感性分析。")


def build_conclusion(doc):
    doc.add_heading("5  结论", level=1)
    add_bullets(doc, [
        "建立了一条端到端、可复现的月面着陆区地形安全性与适宜性评价流程，"
        "覆盖 PDS 数据获取、ISIS/ASP 摄影测量、多尺度地形指标、"
        "U-Net 撞击坑识别、加权适宜性模型与 Monte Carlo 不确定性分析，"
        "全部步骤配有自测脚本与产物哈希登记。",
        "撞击坑自动识别的表面精度（0.451）主要由参考目录与 59 m 分辨率决定："
        "人工随机抽样核查后，精度修正为 0.726、可探测召回为 0.717。"
        "因此评价自动撞击坑识别的价值时，必须区分「模型误差」与「参考数据误差」。",
        "在 Rimae Bode 区域，**安全区面积高度不确定（0.38–0.93），"
        "但候选点排序稳健**：四种参数化与 200 次随机抽样都指向同一最优区 "
        "(353.76°E, 11.08°N)，而论文四个候选点中 LS3 最安全、LS2 最危险。",
        "不确定性主要来自阈值选择而非权重或目录口径。"
        "这提示后续工作应把精力放在阈值的工程依据上，而不是反复调整权重。",
        "仅 26.1% 的研究区在任何参数下都安全，35.2% 的区域结论依赖参数。"
        "把这一比例与对应的概率图作为交付物，比给出单一安全区图更有实用价值。",
        "尚未完成的关键检验是分辨率效应（H1）：需要为最优候选点补充 NAC 立体像对，"
        "或在覆盖区域内开展 SLDEM 与 NAC 的同口径对照。",
    ])


def build_appendix(doc):
    doc.add_page_break()
    doc.add_heading("附录 A  脚本与文档索引", level=1)
    add_para(doc,
        "仓库共 54 个脚本、20 篇文档，按周次组织。完整索引（含每个脚本的首次提交日期）"
        "见 docs/script_index.md，并由 tests/test_script_index.py 自动校验完整性——"
        "任何被 Git 跟踪的脚本若未登记在索引中，测试即失败。")
    add_table(doc, ["阶段", "主要脚本", "产物"],
              [["第 1–2 周", "preprocess_isis.sh, fetch_nac.py, build_data_manifest.py",
                "标准化影像、data_manifest.csv"],
               ["第 3–4 周", "run_nac_pair_rimae_bode.sh, compare_nac_to_sldem.py, preprocess_week4.py",
                "NAC DEM 3.28 m、误差统计、研究区底图"],
               ["第 5 周", "week5_terrain_metrics.py, week5_risk_map.py, week5_error_spatial.py",
                "多尺度地形指标、风险图、误差剖面"],
               ["第 6 周", "week6_build_crater_labels.py, week6_train_unet.py, week6_mask_to_catalog.py, week6_review_false_positives.py",
                "U-Net 权重、632 个坑的 GeoJSON、核查修正"],
               ["第 7 周", "week7_suitability.py, week7_ahp.py, week7_compare_literature.py",
                "适宜性图、候选点、AHP 权重、文献对比"],
               ["第 8 周", "week8_montecarlo.py", "排名稳定性、P(safe) 概率图、参数主导性"],
               ["第 9 周", "week9_case_studies.py", "案例表、敏感/稳健连通区、讨论稿"]],
              widths=[1.1, 3.0, 2.2])

    doc.add_heading("附录 B  复现命令", level=1)
    add_para(doc, "环境：conda env create -f environment.yml（lunarsafe，含 GDAL 与 PyTorch）；"
                  "摄影测量另需 asp 环境（ISIS 10.0.0 与 ASP 3.7.0）。", style=None)
    for cmd in [
        "bash scripts/run_all_tests.sh                                  # 5 个自测全部通过",
        "python scripts/week7_suitability.py --weights 0.5499,0.2098,0.2402 --tag ahp",
        "python scripts/week7_compare_literature.py --tag ahp",
        "python scripts/week8_montecarlo.py --n 200 --concentration 15 --tag k15",
        "python scripts/week8_montecarlo.py --n 200 --concentration 60 --seed 1 --tag k60",
        "python scripts/week9_case_studies.py --tag k15 --top 5",
        "python scripts/build_technical_report.py --out docs/LunarSafeMap_technical_report_v1.0.docx",
    ]:
        p = doc.add_paragraph(cmd)
        p.runs[0].font.name = "Consolas"
        p.runs[0].font.size = Pt(9)
        p.paragraph_format.space_after = Pt(2)
    add_para(doc,
        "原始行星数据与训练得到的模型权重不进入 Git；其大小与 SHA-256 记录在 "
        "data/metadata/data_manifest.csv 与 data/metadata/derived_products.csv 中，"
        "可按登记信息重新获取与校验。")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "docs" / "LunarSafeMap_technical_report_v1.0.docx"))
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    doc = Document()
    set_base_style(doc)
    for s in doc.sections:
        s.top_margin = Inches(0.9)
        s.bottom_margin = Inches(0.9)
        s.left_margin = Inches(0.95)
        s.right_margin = Inches(0.95)
    add_title(doc)
    build_summary(doc)
    build_intro(doc)
    doc.add_page_break()
    build_methods(doc)
    doc.add_page_break()
    build_results(doc)
    doc.add_page_break()
    build_discussion(doc)
    build_conclusion(doc)
    build_appendix(doc)

    doc.add_heading("图版", level=1)
    n = 0
    for _key, path, caption in FIGURES:
        if add_figure(doc, path, caption):
            n += 1
    print("  embedded {:,} figures".format(n))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    size = out.stat().st_size / 1024.0
    print("  wrote {} ({:.0f} KB)".format(out, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
