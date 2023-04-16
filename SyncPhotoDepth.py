import os
import fitdecode
import sys
import datetime
import calendar
import pyexiv2
import argparse
import lat_lon_parser

parser = argparse.ArgumentParser()
parser.add_argument("fitFile", type=str, help="The FIT File to use when sycning depth and temperature to photos")
parser.add_argument("-z", "--timezone", type=str, help="The timezone the photos were taken in, using the format \" -08:00\" to represent something like PST. " + 
                    "NOTE: If timezone offset starts with a leading '-' it must be quoted and have a leading space, as otherwise Python insists on treating it as an optional argument")
parser.add_argument("-o", "--offset", type=int, default = 0, help="Optional picture offset, in seconds, from the FIT file. This is used to offset any clock drift between camera and dive computer" + 
                    "eg. If the Camera clock was 17 seconds behind the Dive Computer Clock you'd pass '-o 17', for an hour and 17 seconds early you'd pass -3617")
parser.add_argument("-l", "--location", type=str, help="Optional human friendly location of the photos to add to the metadata, eg. 'Mukilteo, WA'")
parser.add_argument("-c", "--coords", type=str, help="Optional GPS coordinates to add to the photo. Should be in the form \"##.### -##.###\" I honestly have no idea why this one doesn't always need the leading space when negative.")
parser.add_argument("-F", "--FREEDOM", type=str, default="TRUE", help="Standards are for other people. Why use Meters and C° when Feet and F° exist? Not setting this to false ignores the standard " + 
                    "in favor of using feet and Fahrenheit instead. As the author is from `MERICA, this is the default behaviour. Expects some form of False or 'F', everything else evaluates True " + 
                    "(e.g. -F=YourPartOfTheProbem will evaluate to TRUE and proceed to write everything in Imperial)")
parser.add_argument("-a", "--author", type=str, help="Optional string for Author/Copywrite")
parser.add_argument("-v", "--verbose", action="store_true", help="Flood the console with Print statements")
args = parser.parse_args()

#Create the dictionary for data we'll be adding to photos in advance, because half of it will be identical for all photos so there's no sense updating it in our photo loop
addData = {}

#Get the FIT File name
fFile = args.fitFile
print("FIT File: " + fFile)

#Set timezone for photos cause they're stupid
if args.timezone is not None:
    picTimezone = args.timezone.lstrip()
    print("TimeZone: " + picTimezone)
else:
    picTimezone = None
    print("TimeZone: None")

#Set the picture offset, if present
picOffset = args.offset
if picOffset is not None:
    print("Picture offset (in seconds): " + str(picOffset))
else:
    print("Picture offset (in seconds): None")

#Optional human friendly location to set for photos.
picLoc = args.location
if picLoc is not None:
    print("Picture Location: " + picLoc)
    #Set the "name/location" of the dive. Overloading UniqueID because ReelName isn't displayed by default... <sigh>    
    addData.update({'Exif.Photo.ImageUniqueID': picLoc, 'Exif.Image.ReelName' : picLoc})
else:
    print("Picture Location: None")

#Converts a decimal coordinate into an ugly Degree Minute Second as fractions abomination. hem wants either ["N", "S"] for latitude or ["E", "W"] for longitude
def convertCoord(coord, hem):
    #Because of course EXIF doesn't support signed coordinates, we need to strip negative signs and track them by hemisphere >.<
    if coord.startswith('-'):
        coord = coord[1:]
        ref = hem[1]
    else:
        ref = hem[0]        
        
    #Convert our lovely decimal coordinates into Degrees, Minutes and Seconds
    deg = lat_lon_parser.to_deg_min_sec(lat_lon_parser.parse(coord))
    #Now that we have it as degrees and minutes, we need to convert to fractions because EXIF >.<
    deg = (str(round(deg[0]))+"/1", str(round(deg[1]))+"/1", str(round(deg[2]*100))+"/100")
    return [deg, ref]

#Optional decimal coordinates to set for photos. This will be converted to degrees minutes if not none
if args.coords is not None:
    coords = str.split(args.coords)
    lat = convertCoord(coords[0], ["N", "S"])
    long = convertCoord(coords[1], ["E", "W"])
    picCoords = [lat, long]
    print("GPS Coords: " + str(picCoords))
    #Because of course things cannot be obvous or documented correctly >.< Lat and Long must be passed as a single string of fractions seperated by spaces (NO COMMAS)
    addData.update({"Exif.GPSInfo.GPSLatitude": str(picCoords[0][0][0])+" "+str(picCoords[0][0][1])+" "+str(picCoords[0][0][2]), "Exif.GPSInfo.GPSLatitudeRef": picCoords[0][1],
                    "Exif.GPSInfo.GPSLongitude": str(picCoords[1][0][0])+" "+str(picCoords[1][0][1])+" "+str(picCoords[1][0][2]), "Exif.GPSInfo.GPSLongitudeRef": picCoords[1][1]})
else:
    picCoords = args.coords
    print("GPS Coords: None")

#Optional flag to ignore the EXIF standards in favor of using Feet and Fahrenheit where Meters and Celsius normally go
if 'FALSE'.startswith(args.FREEDOM.upper()) or 'F'.startswith(args.FREEDOM.upper()) :
    ignoreStandards = False
else:
    ignoreStandards = True
print("FREEDOM: " + str(ignoreStandards))

#Get the Author name/Copyright
author = args.author
if author is not None:
    print("Author/Copyright: " + author)
    #Author is apparently a Windows only thing, so setting Copyright as well
    addData.update({'Exif.Image.Copyright': author, 'Exif.Image.XPAuthor': author}) 
else:
    print("Author/Copyright: None")

##Converts Celsius to Fahrenheit if FREEDOM isn't false
def cToF(temp):
    if ignoreStandards:
        return round((temp * 9 / 5 + 32))
    else:
        return temp

#Converts millimeters to feet or meters depending on FREEDOM
def mmToFeet(mm):
    if ignoreStandards:
        return round(mm/304.8)
    else:
        return round(mm/1000,1)

#Sorted list of dive data points
dataPoints = []
#Sorted list of picture files
pictures = []

#Iterates over everything in the current directory and creates a time sorted list of only pictures
for pic in sorted(os.listdir(), key=os.path.getmtime):
    try:
        #Fetch the image metadata so we can grab the date the camera thinks the photo was taken, to ensure we can process these in order taken
        exiv_image = pyexiv2.Image(pic)
        data = exiv_image.read_exif()

        #Get the timestamp the picture was taken
        #Add a timezone because for some dumb reason that isn't stored in EXIF data >.<
        t=datetime.datetime.strptime(data['Exif.Image.DateTime'] + picTimezone, '%Y:%m:%d %H:%M:%S%z')
        #Close the image because the library tells us to
        exiv_image.close()
        #Convert to Epoch so we can stop dealing with the pain that is DateTime objects
        pictures.append((pic, (t.timestamp() + picOffset)))
    except:
        continue
#Sort the pictures by their metadata created date, just in case the OS was sorting by a different timestamp
pictures.sort(key = lambda x: x[1])

#Loop to go through .fit file and pull out the timestamp, depth, and temp of each known point of the dive, then sort
#them by time (nearest second). Also converts Celsius to Fahrenheit, rounding to nearest integer
with fitdecode.FitReader(fFile) as fit_file:
    for frame in fit_file:
        if isinstance(frame, fitdecode.records.FitDataMessage):
            if frame.name == 'record':
                # This frame contains point in time dive data.
                for field in frame.fields:                    
                    if field.name == 'timestamp':
                        #Get the Date and convert it to an epoch time. DON'T use raw_value cause they are doing something funky and it isn't standard >.<    
                        ts = calendar.timegm(field.value.timetuple())
                    elif field.name == 'depth':
                        #We'll leave it as mm for now and convert after we average out the depth between the two data points
                        mm = str(field.raw_value)
                    elif field.name =='temperature':
                        #Grab the raw Celsius temp and convert it to Fahrenheit
                        temp = str(cToF(field.raw_value))
                dp = (ts, mm, temp)
                dataPoints.append(dp)
dataPoints.sort()

# Nested loop that iterates through the pictures and datapoints in "Created" sorted order, iterating datapoints until it finds
# a datapoint that is newer than the current photo, then normalizes the depth between the newer and older datapoint to guestimate
# the depth the photo was taken
k = 0
for pic in pictures:
    while dataPoints[k][0] < pic[1]:
        k = k + 1
        if(k == len(dataPoints)):
            break
    #Apparently Python can't break out of nested loops, so double check for each photo
    if(k == len(dataPoints)):
        break
    #If the datapoint and photo happened close enough together, proceed to assign metadata
    if (dataPoints[k][0] - pic[1]) <= 10:
        nextDepth = int(dataPoints[k][1])
        prevDepth = int(dataPoints[k-1][1])
        #Determine the time difference between datapoints (for readability)
        timeRange = dataPoints[k][0] - dataPoints[k-1][0]
        #Determine where the photo falls between datapoints to guestimate depth
        offset = dataPoints[k][0] - pic[1]
        #Calculate the depth assuming a linear change between the two points, then convert to feet. Convert to a fraction because apparently that is required to work
        depth = str(mmToFeet(nextDepth - ((nextDepth - prevDepth)/(timeRange) * (offset)))) + "/1"
        if args.verbose:
            print("Found depth: " + str(depth))
        
        # Create set of metadata we wish to update. This will overwrite its original value, or add it if it doesn't exist
        addData.update({'Exif.Photo.WaterDepth': depth, #WaterDepth (Technically supposed to be in meters, buuuutt.... 'MERICA!)
                   #Temperature also supposed to be in Celsius, but that's just silly. Almost as silly as the fact that it must be saved as a fraction, as opposed to a float or something sane.
                   'Exif.Photo.Temperature': str(dataPoints[k][2]) + "/1", 
                   #Set the Altitude, because WaterDepth doesn't actually show up >.< Ref of 1 indicates Altitude is below sea level (sadly it is the absolute value so will display as positive number)
                   'Exif.GPSInfo.GPSAltitudeRef': 1, 'Exif.GPSInfo.GPSAltitude': depth})
        if args.verbose:
            print(addData)

        #Fetch the metadata object we wish to edit
        image = pyexiv2.Image(pic[0])
        image.modify_exif(addData)
        #Close the image cause the library people said we get memory leaks otherwise
        image.close