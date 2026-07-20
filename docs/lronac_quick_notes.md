# LRO NAC Quick Stereo Baseline

This note records the first ASP lunar stereo reconstruction baseline.

## Purpose

Reproduce a minimal lunar stereo workflow with NASA Ames Stereo Pipeline:

1. LRO NAC stereo images
2. CSM camera models
3. Stereo matching
4. Point cloud generation
5. DEM rasterization
6. Orthoimage and triangulation error output

## Environment

- WSL2 Ubuntu 24.04
- ASP 3.7.0
- ISIS 10.0.0
- GDAL 3.12.2

## Key Outputs

- `run-PC.tif`: ASP point cloud
- `run-DEM.tif`: digital elevation model
- `run-DRG.tif`: orthoimage
- `run-IntersectionErr.tif`: triangulation intersection error

## First Result

The first run produced a DEM with about 95.23% valid pixels.

The intersection error percentiles reported by `point2dem` were:

- Q1: 7.97 m
- Q2: 8.07 m
- Q3: 8.07 m

These errors describe stereo ray intersection consistency, not absolute DEM accuracy.

## Notes

The DRG may look black when opened directly because of display stretch. This is a visualization issue, not necessarily a failed product. Use QGIS min/max stretch or convert with proper scaling.
cd ~/projects/LunarSafeMap

gdalinfo -stats examples/lronac_quick/LRONAC_example/run/run-DEM.tif > docs/lronac_quick_dem_gdalinfo.txt
gdalinfo -stats examples/lronac_quick/LRONAC_example/run/run-IntersectionErr.tif > docs/lronac_quick_intersection_error_gdalinfo.txt


