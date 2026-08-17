This fully self-contained and ready-made example shows how to use the
NASA Ames Stereo Pipeline with Lunar data. This example uses images
from the LRO NAC camera with CSM camera models, described at. 

    https://stereopipeline.readthedocs.io/en/latest/examples.html#community-sensor-model-csm
    
How to run:

 - Fetch and install the latest daily build per:

    https://stereopipeline.readthedocs.io/en/latest/installation.html

 - Fetch and extract this dataset as:
  
    wget https://github.com/NeoGeographyToolkit/StereoPipelineSolvedExamples/releases/download/LRONAC/LRONAC_example.tar

    tar xfv LRONAC_example.tar
    cd LRONAC_example

- Start stereo_gui with a selected clip:

   stereo_gui M181058717LE_crop.cub M181073012LE_crop.cub \
     M181058717LE.json M181073012LE.json                  \
     --alignment-method local_epipolar                    \
     --left-image-crop-win 2259 1196 900 973              \
     --right-image-crop-win 2432 1423 1173 1218           \
     --stereo-algorithm asp_mgm                           \
     run/run

The crop windows from above will show up as red rectangles. The GUI
program is described in more detail at:

    https://stereopipeline.readthedocs.io/en/latest/tools/stereo_gui.html

Choose from the menu ``Run -> Run parallel_stereo``. When finished,
quit the GUI and run from the command line:

    point2dem --errorimage run/run-PC.tif --orthoimage run/run-L.tif

Open the computed DEM and orthoimage as:

   stereo_gui run/run-DEM.tif run/run-DRG.tif

Right-click on the DEM on the left and choose to toggle hillshading to
show the DEM hillshaded.

Higher quality results can be obtained by adding to ``parallel_stereo``
the option ``--subpixel-mode 2``, but that will be quite a bit slower.

Compare with the precomputed results at:

  sample_run/run-DEM.tif sample_run/run-DRG.tif
