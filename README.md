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
ASP environment
Used for lunar stereo reconstruction and DEM generation.
conda activate asp
Verified version:
NASA Ames Stereo Pipeline 3.7.0
USGS ISIS 10.0.0
GDAL 3.12.2
##Research Direction
The next goal is to move from tool reproduction to a research-oriented workflow:
DEM quality assessment
Slope and roughness calculation
Scale and resolution sensitivity analysis
Lunar landing site terrain safety evaluation
Uncertainty analysis of terrain-derived safety maps
Data Policy
Large planetary data products are not committed to Git.
Raw data, intermediate products, ASP outputs, and model weights should remain outside the repository or be documented through metadata and download instructions.
```bash
conda activate lunarsafe

