import os
from pathlib import Path
import fitdecode
import sys
import datetime
import calendar
import pyexiv2
import argparse
import lat_lon_parser
from collections import namedtuple


parser = argparse.ArgumentParser()
parser.add_argument("-f", "--fitFile", type=str, help="The FIT File to use when sycning depth and temperature to photos. If supplied, program will ONLY update photos that fall within the time period" + 
                    "of the provided .fit file. If left blank, then ALL photos found in the directory will have their metadata updated.")
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
parser.add_argument("-d", "--description", type=str, help="Optional string for Description")
parser.add_argument("-C", "--comment", type=str, help="Optional string for XPComment")
parser.add_argument("-J", "--subject", type=str, help="Optional string for XPSubject")
parser.add_argument("-p", "--path", type=str, help="Path to the folder containing the photos you wish to update. If left blank assumes working directory")
parser.add_argument("-v", "--verbose", action="store_true", help="Flood the console with Print statements")
args = parser.parse_args()



#Create the dictionary for data we'll be adding to photos in advance, because half of it will be identical for all photos so there's no sense updating it in our photo loop
addData = {}


picPath = os.getcwd()
#Get the location of pictures to edit
if args.path:
    picPath = args.path
    print(f"Photo location: {picPath}")
else:
    print("No PATH defined, using current working directory.")

fFile = None
#Get the FIT File name
if args.fitFile:
    fFile = args.fitFile
    print("FIT File: " + fFile)
else:
    print("No .fit File supplied, will scan photo directory for .fit files to use.")

#Set timezone for photos cause they're stupid
if args.timezone:
    picTimezone = args.timezone.lstrip()
    print("TimeZone: " + picTimezone)
else:
    picTimezone = "+00:00"
    print("TimeZone: None")

#Set the picture offset, if present
picOffset = args.offset
if picOffset:
    print("Picture offset (in seconds): " + str(picOffset))
else:
    print("Picture offset (in seconds): None")

#Optional human friendly location to set for photos.
picLoc = args.location
if picLoc:
    print("Picture Location: " + picLoc)
    #Set the "name/location" of the dive. Overloading UniqueID because ReelName isn't displayed by default... <sigh>    
    addData.update({'Exif.Photo.ImageUniqueID': picLoc, 'Exif.Image.ReelName' : picLoc})
else:
    print("Picture Location: None")

# Creating a Named Coordinate Tuple
Coord = namedtuple('Coord', ['deg', 'min', 'sec'])

# Creating a Named L*tude Tuple
Ltude = namedtuple('Ltude', ['coord', 'ref'])

def convertCoord(coord, hem):
    '''Converts a decimal coordinate into an ugly Degree Minute Second as fractions abomination. 
       @coord - A single decimal coordinate, like '-122.30292438387733' to be converted
       @hem - Either the array ["N", "S"] for latitude or ["E", "W"] for longitude'''
    #Because of course EXIF doesn't support signed coordinates, we need to strip negative signs and track them by hemisphere >.<
    if coord.startswith('-'):
        coord = coord[1:]
        ref = hem[1]
    else:
        ref = hem[0]        
        
    #Convert our lovely decimal coordinates into Degrees, Minutes and Seconds
    deg = lat_lon_parser.to_deg_min_sec(lat_lon_parser.parse(coord))
    #Now that we have it as degrees and minutes, we need to convert to fractions because EXIF >.<
    deg = Coord(str(round(deg[0]))+"/1", str(round(deg[1]))+"/1", str(round(deg[2]*100))+"/100")
    return Ltude(deg, ref)

#Optional decimal coordinates to set for photos. This will be converted to degrees minutes if not none
if args.coords:
    print(f"GPS Coords: {args.coords}")
    coords = str.split(args.coords)
    lat = convertCoord(coords[0], ["N", "S"])
    long = convertCoord(coords[1], ["E", "W"])
    picCoords = [lat, long]
    if(args.verbose):
        print(f'GPS Coords: {" ".join(picCoords[0].coord)} {picCoords[0].ref}, {" ".join(picCoords[1].coord)} {picCoords[1].ref}')    
    #Because of course things cannot be obvous or documented correctly >.< Lat and Long must be passed as a single string of fractions seperated by spaces (NO COMMAS)
    addData.update({"Exif.GPSInfo.GPSLatitude": " ".join(picCoords[0].coord), "Exif.GPSInfo.GPSLatitudeRef": picCoords[0].ref,
                    "Exif.GPSInfo.GPSLongitude": " ".join(picCoords[1].coord), "Exif.GPSInfo.GPSLongitudeRef": picCoords[1].ref})
else:
    picCoords = args.coords
    print("GPS Coords: None")

#Optional flag to ignore the EXIF standards in favor of using Feet and Fahrenheit where Meters and Celsius normally go
if 'FALSE'.startswith(args.FREEDOM.upper()) or 'F'.startswith(args.FREEDOM.upper()) :
    ignoreStandards = False
else:
    ignoreStandards = True
print("FREEDOM: " + str(ignoreStandards))

#Get the Description
description = args.description
if description:
    print(f"Description: {description}")
    #Author is apparently a Windows only thing, so setting Copyright as well
    addData.update({'Exif.Image.ImageDescription': description}) 
else:
    print("Description: None")

#Get the Author name/Copyright
author = args.author
if author:
    print("Author/Copyright: " + author)
    #Author is apparently a Windows only thing, so setting Copyright as well
    addData.update({'Exif.Image.Copyright': author, 'Exif.Image.XPAuthor': author}) 
else:
    print("Author/Copyright: None")

#Get the Subject
subject = args.subject
if subject:
    print("Subject: " + subject)
    #Subject is apparently a Windows only thing, hopefully Mac users can just ignore it?
    addData.update({'Exif.Image.XPSubject': subject}) 
else:
    print("Subject: None")

#Get the Comment
comment = args.comment
if comment:
    print("Comment: " + comment)
    #Comment is apparently a Windows only thing, hopefully Mac users can just ignore it?
    addData.update({'Exif.Image.XPComment': comment}) 
else:
    print("Comment: None")

def cToF(temp):
    '''Converts Celsius to Fahrenheit if FREEDOM isn't false, rounds to the nearest whole number'''
    if ignoreStandards:
        return round((temp * 9 / 5 + 32))
    else:
        return temp

def mmToFeet(mm):
    '''Converts millimeters to feet or meters depending on FREEDOM, rounded to the near whole number'''
    if ignoreStandards:
        return round(mm/304.8)
    else:
        return round(mm/1000,1)
    
def updatePhoto(photo, addData):
    ''' Updates the provided photo with the desired metadata
        @photo - Path of the photo to update
        @addData - Dictionary of metadata desired to be added/updated'''
    
    if args.verbose:
        print(f"Updating photo: {photo}")
    #Fetch the metadata object we wish to edit
    image = pyexiv2.Image(photo)
    image.modify_exif(addData)
    #Close the image cause the library people said we get memory leaks otherwise
    image.close    

    #Pyexiv re-encodes anything starting with XP and modifies the original dictionary with the new value, causing the loop to spiral out of control. To combat that, reset XPAuthor now if it was used
    if author:
        addData.update({'Exif.Image.XPAuthor': author}) 

        
# Creating a Named DataPoint Tuple
DataPoint = namedtuple('DataPoint', ['time', 'depth', 'temp'])
#Sorted list of dive data points
dataPoints = []
#Sorted list of picture files
pictures = []

def parseFitFile(fitFile):
    ''' Loop to go through .fit file and pull out the timestamp, depth, and temp of each known point of the dive, then sort
        them by time (nearest second). Also converts Celsius to Fahrenheit, rounding to nearest integer
        @fitFile - .fit File to parse and add to the dataPoints collection'''
    with fitdecode.FitReader(fitFile) as fit_file:
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
                    dp = DataPoint(ts, mm, temp)
                    dataPoints.append(dp)
    dataPoints.sort()
    if args.verbose:
        print(f"First Datapoint: {dataPoints[0].time}")
        print(f"Last Datapoint: {dataPoints[len(dataPoints) -1].time}")

#If a .fit file was supplied, load it now
if fFile:
    parseFitFile(fFile)

c = 0
#Iterates over everything in the current directory and creates a time sorted list of only pictures
for pic in sorted(Path(picPath).iterdir(), key=os.path.getmtime):
    c = c + 1
    if c % 100 == 0:
        print(f"Scanned {c} files so far.")
    #Don't actually want a path cause most libraries seem to expect a String
    pic = str(pic)
    if args.verbose:
        print(f"Attempting File: {pic}")
    
    if not fFile and pic.upper().endswith(".FIT"):
        print(f"Found .fit file {pic}, attempting to parse.")
        parseFitFile(pic)
        continue
    try:
        #Fetch the image metadata so we can grab the date the camera thinks the photo was taken, to ensure we can process these in order taken
        exiv_image = pyexiv2.Image(pic)
        data = exiv_image.read_exif()

        #Get the timestamp the picture was taken. Try it twice cause apparently there are lots of these fields sprinkled all over the EXIF dataset people can use >.<
        #Add a timezone because for some dumb reason that isn't stored in EXIF data >.<
        try:
            t=datetime.datetime.strptime(data['Exif.Image.DateTime'] + picTimezone, '%Y:%m:%d %H:%M:%S%z')
        except KeyError:
            t=datetime.datetime.strptime(data['Exif.Photo.DateTimeOriginal'] + picTimezone, '%Y:%m:%d %H:%M:%S%z')            
        if args.verbose:
            print(f"Photo: {pic} {t} {t.timestamp()}")
        #Close the image because the library tells us to
        exiv_image.close()
        #Convert to Epoch so we can stop dealing with the pain that is DateTime objects
        pictures.append((pic, (t.timestamp() + picOffset)))
    except RuntimeError:
        continue
    except KeyError:
        print(f"Couldn't parse the Exif.Image.DateTime for {pic}, skipping.")
        print(data)
        continue
#Sort the pictures by their metadata created date, just in case the OS was sorting by a different timestamp
pictures.sort(key = lambda x: x[1])
print(f"Found {len(pictures)} pictures to update.")

#Quick check if we had any .fit files, if not update all the photos with the bulk data and abort the script early
if not dataPoints:
    for pic in pictures:
        #Update the photo 
        updatePhoto(pic[0], addData)
    sys.exit()

# Nested loop that iterates through the pictures and datapoints in "Created" sorted order, iterating datapoints until it finds
# a datapoint that is newer than the current photo, then normalizes the depth between the newer and older datapoint to guestimate
# the depth the photo was taken
k, c = 0, 0
fitKeys = ['Exif.Photo.WaterDepth','Exif.Photo.Temperature','Exif.GPSInfo.GPSAltitudeRef', 'Exif.GPSInfo.GPSAltitude']
for pic in pictures:
    c = c + 1
    if c % 100 == 0:
        print(f"Updated {c} photos so far.")
    #If we have .fit data, then determine what belongs to this photo
    try:
        #Because both fit data and pictures are in chronological order, as long as the datapoint is older than the photo increment it. This means pictures older than the oldest fit data will skip
        #this loop, which is fine that just means we don't have data for them. Likewise photos taken after the .fit data will quickly exceed the diff limit and bypass the fit checks as well.
        while k < (len(dataPoints)-1) and dataPoints[k].time < pic[1]:
            k = k + 1        
        #If the datapoint and photo happened close enough together, proceed to assign metadata
        if abs(dataPoints[k].time - pic[1]) <= 10:
            nextDepth = int(dataPoints[k].depth)
            prevDepth = int(dataPoints[k-1].depth)
            #Determine the time difference between datapoints (for readability)
            timeRange = dataPoints[k].time - dataPoints[k-1].time
            #Determine where the photo falls between datapoints to guestimate depth
            offset = dataPoints[k].time - pic[1]
            #Calculate the depth assuming a linear change between the two points, then convert to feet. Convert to a fraction because apparently that is required to work
            depth = str(mmToFeet(nextDepth - ((nextDepth - prevDepth)/(timeRange) * (offset)))) + "/1"
            if args.verbose:
                print("Found depth: " + str(depth))
            
            # Create set of metadata we wish to update. This will overwrite its original value, or add it if it doesn't exist
            addData.update({'Exif.Photo.WaterDepth': depth, #WaterDepth (Technically supposed to be in meters, buuuutt.... 'MERICA!)
                    #Temperature also supposed to be in Celsius, but that's just silly. Almost as silly as the fact that it must be saved as a fraction, as opposed to a float or something sane.
                    'Exif.Photo.Temperature': str(dataPoints[k].temp) + "/1", 
                    #Set the Altitude, because WaterDepth doesn't actually show up >.< Ref of 1 indicates Altitude is below sea level (sadly it is the absolute value so will display as positive number)
                    'Exif.GPSInfo.GPSAltitudeRef': 1, 'Exif.GPSInfo.GPSAltitude': depth})
            if args.verbose:
                print(addData)

        #If we didn't find a photo in our .fit range we need to clear the previous fit data before it claims it
        elif addData.get('Exif.Photo.WaterDepth'):
            for key in fitKeys:
                del addData[key]
    except IndexError:        
        break
    
    #Update the photo 
    updatePhoto(pic[0], addData)

