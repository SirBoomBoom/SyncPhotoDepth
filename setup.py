from distutils.core import setup
import py2exe
   
setup(
    console=['SyncPhotoDepth.py'],
    options={
        "py2exe":{            
            "packages":["pyexiv2"]
        }
    }
)
        