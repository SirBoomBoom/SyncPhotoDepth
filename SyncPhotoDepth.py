import os
import fitdecode
import sys
import datetime
import calendar
import pytz
from exif import Image as ExifImage
from PIL import Image as PillowImage
from PIL import ExifTags

# Remove 1st argument from the list of command line arguments
argumentList = sys.argv[1:]
#Parse arguments
#'ScubaDiving_2023-02-20T14_19_15.fit'
fFile = argumentList[0]

#Set timezone for photos cause their stupid
#picTimezone = pytz.timezone(argumentList[1])
picTimezone = argumentList[1]

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
        pil = PillowImage.open(pic)
        #Get the timestamp the picture was taken
        #Add a timezone because for some dumb reason that isn't stored in EXIF data >.<
        t=datetime.datetime.strptime(pil.getexif()[306] + picTimezone, '%Y:%m:%d %H:%M:%S%z')        
        #Convert to GMT because for lord knows what reason Python completely ignores the timezone when converting to UTC >.<
        rage = t.astimezone(pytz.timezone('GMT'))         
        #Convert to Epoch so we can stop dealing with the pain that is DateTime objects
        pictures.append((pic, calendar.timegm(rage.timetuple())))
    except:
        continue
#Sort the pictures by their metadata created date, just in case the OS was sorting by a different timestamp
pictures.sort(key = lambda x: x[1])

#Loop to go through .fit file and pull out the timestamp, depth, and temp of each known point of the dive, then sort
#them by time (nearest second). Also converts mm to feet and Celsius to Fahrenheit, rounding each to nearest integer
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
                        #Get the raw depth data (in mm) and conver to feet since we are rounding to the nearest 10 seconds anyways
                        #ft = str(mmToFeet(field.raw_value))
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
        #Calculate the depth assuming a linear change between the two points, then convert to feet
        depth = mmToFeet(nextDepth - ((nextDepth - prevDepth)/(dataPoints[k][0] - dataPoints[k-1][0]) * (dataPoints[k][0] - pic[1])))
        print("Found depth: " + str(depth))        

        pillow_image = PillowImage.open(pic[0])
        img_exif = pillow_image.getexif()

        #WaterDepth (Technically supposed to be in meters, buuuutt.... 'MERICA!)
        img_exif[37891] = depth
        #Temperature also supposed to be in Celsius, but that's just silly
        img_exif[37888] = dataPoints[k][2]

        img_exif[33432] = "Don Mitchell"
        


        output_file = "test/" + pic[0]
        pillow_image.save(output_file, exif=img_exif)   
        