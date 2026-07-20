# LunarSafeMap

LunarSafeMap is an undergraduate research project for learning and reproducing planetary remote sensing and deep-space mapping workflows.

The current stage focuses on a minimal lunar stereo photogrammetry baseline with NASA Ames Stereo Pipeline (ASP), using LRO NAC stereo images to generate a point cloud, DEM, orthoimage, and triangulation error map.

## Current Progress

- Set up WSL2 Ubuntu 24.04
- Created a reproducible Python geospatial environment
- Installed NASA Ames Stereo Pipeline 3.7.0 with ISIS 10.0.0
- Reproduced the official LRO NAC quick stereo example
- Generated:
  - point cloud
  - DEM
  - orthoimage
  - triangulation intersection error map
- Documented the first DEM quality check

## Environments

### Python geospatial environment

Used for raster processing, GIS, terrain analysis, and later machine learning.

```bash
conda activate lunarsafe
