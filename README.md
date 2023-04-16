# SyncPhotoDepth
Python Project to sync temperature and dive depth information from a .FIT file to photos taken at the same time by editing the EXIF data

This is meant to synch data from a .FIT file with corresponding photos from the same activity. It functions by first creating a list of all photos in the current directory, sorted by their created date and then iterating through the FIT data (again chronological order) to attempt to find the two datapoints closest to the time the photo was taken. Once found, the datapoints are averaged together and the new depth and temperature are added to the photos metadata. Since any meaningful depth of water blocks GPS data I make no effort to try and average location data, if someone had an example FIT file with GPS data embedded in it I could probably be convinced.

Things to note: 
* Currently code expects that datapoints were taken within 10 seconds of the photo, anything greater is ignored as not having an applicable datapoint.
* Program defaults to FREEDOM mode, which ignores the EXIF standard in favor of using Feet and Fahrenheit where Meters and Celsius would normally be used. This can be disabled with -F=False
* "Averages" are calculated by taking the timestampt difference between the two data points, in seconds, and then assuming a linear change between the two. The difference between the photo and the first datapoint is then calculated and multiplied by the second step delta to determine the new value. 
* This updates the photos in place, so a backup is recommended before messing with this just in case

There is only one required parameter, which is the name of the .FIT file to use for synching.

Otherwise there are several optional parameters that can be used to add additional data to all photos in the collection, including Author, a friendly location name (e.g. "Mom's House" or "New York, NY"), and actual GPS decimal coordinates

-z --timezone TIMEZONE 
* The timezone the photos were taken in, using the format " -08:00" to represent something like PST. NOTE: If timezone offset starts with a leading '-' it must be quoted and have a leading space, as otherwise Python insists on treating it as an optional argument

-o --offset OFFSET
* Optional picture offset, in seconds, from the FIT file. This is used to offset any clock drift between camera and dive computereg. If the Camera clock was 17 seconds behind the Dive Computer Clock you'd pass '-o 17', for an hour and 17 seconds early you'd pass -3617

-l --location LOCATION
* Optional human friendly location of the photos to add to the metadata, eg. 'Mukilteo, WA'

-c --coords COORDS
* Optional GPS coordinates to add to the photo. Should be in the form "##.### -##.###" I honestly have no idea why this one doesn't always need the leading space when negative.

-F --FREEDOM FREEDOM
* Standards are for other people. Why use Meters and C° when Feet and F° exist? Not setting this to false ignores the standard in favor of using feet and Fahrenheit instead. As the author is from 'MERICA, this is the default behaviour. Expects some form of False or 'F', everything else evaluates True (e.g. -F=YourPartOfTheProbem will evaluate to TRUE and proceed to write everything in Imperial)

-a --author AUTHOR
* Optional string for Author/Copywrite

-v, --verbose
* Flood the console with Print statements


Example execution:

SyncPhotoDepth.py ScubaDiving_2023-02-20T14_19_15.fit -z " -07:00" -l "Mukilteo, Washington" -c "47.95007464778781 -122.30292438387733" --author=SirBoomBoom