
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
