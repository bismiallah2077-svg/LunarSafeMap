
**README_CN.md**

```markdown
# LunarSafeMap

LunarSafeMap 是一个面向行星遥感与深空测绘方向的本科科研训练项目。

当前阶段的目标是复现 NASA Ames Stereo Pipeline（ASP）的月球立体测图流程，使用 LRO NAC 月球立体影像生成点云、DEM、正射影像和三角交会误差图。

## 当前进展

已经完成：

- WSL2 Ubuntu 24.04 环境配置
- Python 遥感与地理空间环境搭建
- NASA Ames Stereo Pipeline 3.7.0 安装
- ISIS 10.0.0 环境验证
- LRO NAC 月球快速立体案例复现
- 点云、DEM、正射影像、交会误差图生成
- 初步记录 DEM 与误差图统计信息

## 环境

### Python 遥感环境

用于后续栅格处理、地形分析、GIS 操作和机器学习实验。

```bash
conda activate lunarsafe
主要工具包括 Rasterio、GDAL、GeoPandas、NumPy、SciPy、OpenCV、scikit-image 等。
ASP 环境
用于月球立体测图、点云生成和 DEM 生产。
conda activate asp
已验证版本：
NASA Ames Stereo Pipeline 3.7.0
USGS ISIS 10.0.0
GDAL 3.12.2
LRO NAC 快速立体测图基线
当前第一个基线案例来自 ASP 官方 LRO NAC 月球快速示例。
运行脚本：
scripts/run_lronac_quick_example.sh
关键输出：
run-PC.tif                 点云
run-DEM.tif                数字高程模型
run-DRG.tif                正射影像
run-IntersectionErr.tif    三角交会误差图
后续研究方向
下一步将从“工具复现”推进到“研究问题验证”：
DEM 质量检查
坡度与粗糙度计算
空间分辨率敏感性分析
月球候选着陆区地形安全性评价
地形误差与评价结果不确定性分析
数据管理原则
不把大型行星数据直接提交到 GitHub。
原始影像、ISIS 数据、中间结果、ASP 输出和模型权重应保存在本地数据目录或移动硬盘中，仓库只记录数据来源、处理脚本、参数和小型说明文件。
