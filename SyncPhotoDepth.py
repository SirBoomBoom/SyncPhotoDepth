import os
import fitdecode
import sys
import datetime
import calendar
import pyexiv2

# Remove 1st argument from the list of command line arguments
argumentList = sys.argv[1:]
#Parse arguments
fFile = argumentList[0]

#Set timezone for photos cause they're stupid
picTimezone = argumentList[1]

#Optional human friendly location to set for photos. Should probably make this a '-l/-loc' type option...
picLoc = argumentList[2]

##Converts Celsius to Fahrenheit
def cToF(temp):
    return round((temp * 9 / 5 + 32))

#Converts millimeters to feet
def mmToFeet(mm):
    return round(mm/304.8)

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
        pictures.append((pic, t.timestamp()))
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
        print("Found depth: " + str(depth))
        
        # Create set of metadata we wish to update. This will overwrite its original value, or add it if it doesn't exist
        addData = {'Exif.Image.Copyright': "Don Mitchell",
                   # #WaterDepth (Technically supposed to be in meters, buuuutt.... 'MERICA!)
                   'Exif.Photo.WaterDepth': depth, 
                   #Temperature also supposed to be in Celsius, but that's just silly. Almost as silly as the fact that it must be saved as a fraction, as opposed to a float or something sane.
                   'Exif.Photo.Temperature': str(dataPoints[k][2]) + "/1", 
                   #Set the Altitude, because WaterDepth doesn't actually show up >.< Ref of 1 indicates Altitude is below sea level (sadly it is the absolute value so will display as positive number)
                   'Exif.GPSInfo.GPSAltitudeRef': 1, 'Exif.GPSInfo.GPSAltitude': depth,
                   #Set the "name/location" of the dive. Overloading UniqueID because ReelName isn't displayed by default... <sigh>
                   'Exif.Photo.ImageUniqueID': picLoc, 'Exif.Image.ReelName' : picLoc}

        #Fetch the metadata object we wish to edit
        image = pyexiv2.Image(pic[0])
        image.modify_exif(addData)
        #Close the image cause the library people said we get memory leaks otherwise
        image.close