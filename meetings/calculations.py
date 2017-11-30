import arrow
import logging

#This function takes a gcal service, a list of calendars, and a dateTime range and returns
# a list of all events from the list of calendars that fall within or overlap that dateTime range
def getEventsFromAllCalendars(gcal_service, calendars, begin, begin_time, end, end_time):
    b_hrs, b_mins = begin_time.split(':')
    e_hrs, e_mins = end_time.split(':')
    showEvents = []

    # Get all events from the given calendars
    for calendar in calendars:
        calendarID = str(calendar)
        page_token = None
        # For each day in the given date range on the given calendar (sorted)
        for day in arrow.Arrow.span_range('day', begin, end):

            day_start = arrow.get(day[0])
            day_end = arrow.get(day[1])

            #While there are still more events to get
            while True:
                #Get the appropriate time range
                current_begin = day[0].shift(hours=+int(b_hrs), minutes=+int(b_mins))
                current_end = day[1].replace(hour=int(e_hrs), minute=int(e_mins))
                events = gcal_service.events().list(calendarId=calendarID, pageToken=page_token, timeMax=current_end, timeMin=current_begin).execute()
                
                #For each event in the list of events
                for event in events['items']:
                    eventStart = event['start']
                    eventFinish = event['end']
                    #Check for transparent events
                    if 'transparency' in event and event['transparency'] == "transparent":
                        continue
                    showEvents.append(event)
                page_token = events.get('nextPageToken')
                if not page_token:
                   break
    #end get all events from given calendars
    
    #get individual event details
    finished_events = [ ]
    for event in showEvents:
        eventDetails = []
        #If the event has a start time, it is not an all day event
        if 'dateTime' in event['start']:
            start_time = arrow.get(event['start']['dateTime'])
            end_time = arrow.get(event['end']['dateTime'])
        #Event is all day, so don't try to parse times
        else:
            start_time = arrow.get(event['start']['date'])
            start_time = start_time.replace(tzinfo='US/Pacific', hour=int(b_hrs), minute=int(b_mins))
            end_time = start_time.replace(hour=int(e_hrs), minute=int(e_mins))
        #end if/else statement
        #create a list of event summaries and their start/end times
        eventDetails = [start_time, end_time, event['summary']]
        finished_events.append(eventDetails)     
    #endfor

    return finished_events

def getBlocks(eventList, beginDate, beginTime, endDate, endTime):
    b_hrs, b_mins = beginTime.split(':')
    e_hrs, e_mins = endTime.split(':')

    #sort the list of events by start time
    sortedEvents = sorted(eventList, key=lambda k: k[0])

    #create an empty list to store the blocks in
    already_processed = [ ]

    for day in arrow.Arrow.span_range('day', beginDate, endDate):
        for time_block in sortedEvents:
            joined = False
            if time_block[0] > day[0] and time_block[1] < day[1]:
                for current_block in already_processed:
                    if current_block[0] > day[0] and current_block[1] < day[1]:
                        # if time_block start time is later than current_block start time
                        if time_block[0] > current_block[0]:
                            # if time_block end time is later than current_block end time
                            if time_block[1] > current_block[1]:
                                current_block[1] = time_block[1]
                                joined = True
                            # time_block end time is earlier than current_block end time
                            else:
                                joined = True

                        # if time_block end time is earlier current_block end time
                        elif time_block[1] < current_block[1]:
                            #if time_block start time is earlier current_block start time
                            if time_block[0] < current_block[0]:
                                current_block[0] = time_block[0]
                                joined = True
                        #if time block start time is earlier than current block start
                        elif time_block[0] < current_block[0]:
                            # AND time block end is later than current block end
                            if time_block[1] > current_block[1]:
                                current_block[0] = time_block[0]
                                current_block[1] = time_block[1]
                                joined = True
                    
                #endfor current_block
                if not joined:
                    already_processed.append(time_block)
        #endfor time_block
    #endfor day in range

    #get free blocks from the list of 
    free_times = []
    index = 0
    for day in arrow.Arrow.span_range('day', beginDate, endDate):
        begin_time = day[0].shift(hours=+int(b_hrs), minutes=+int(b_mins))
        end_time = day[1].replace(hour=int(e_hrs), minute=int(e_mins))
        block_begin = begin_time
        block_end = end_time
        handled = False
        while index < len(already_processed):
            #if the current block's begin time is before or at the end time of the day
            #then it is an event in this day
            if already_processed[index][0] <= end_time:
                #if the current block's end time is before the end of the day
                #then there might be another block
                if already_processed[index][1] < end_time:
                    free_block = [block_begin, already_processed[index][0], "Available"]
                    free_times.append(free_block)
                    block_begin = already_processed[index][1]
                    index += 1
                    handled = True
                else:
                    if already_processed[index][0] < begin_time:
                        index += 1
                        handled = True
                        continue
                    #the end time is after the end of the day range, we've reached the end of the day
                    free_block = [block_begin, already_processed[index][0], "Available"]
                    free_times.append(free_block)
                    index += 1
                    handled = True
                    break
            else:
                free_block = [block_begin, block_end, "Available"]
                free_times.append(free_block)
                handled = True
                break
        #endwhile
        #If I got to the end of a day and didn't handle that day in some way shape or form
        #it's a free day
        if handled == False:
            free_block = [block_begin, block_end]
            free_times.append(free_block)
    #endfor

        #remove any free blocks that are shorter than specified meeting duration
        #duration is in minutes
    duration = 1
    free_times = crop(free_times, duration)

    #concatenate the two lists
    finishedBlocks =[ ]
    index = 0
    for freeBlock in free_times:
        handled = False
        while index < len(sortedEvents):
            #if a busy block ends after free block begins
            #then the busy block is after the free block
            if sortedEvents[index][1] > freeBlock[0]:
                finishedBlocks.append(freeBlock)
                handled = True
                break
            else:
                finishedBlocks.append(sortedEvents[index])
                index += 1
        #endwhile
        if handled == False:
            finishedBlocks.append(free_block)
    for busyBlock in sortedEvents:
        if busyBlock not in finishedBlocks:
            finishedBlocks.append(busyBlock)
            
    # Wow, we're finally done
    return finishedBlocks


def getPertinentInfo(eventList):
#Take a list of free and busy times and deconstruct them into their pertinent information for displaying on the web application
    #current format of event in eventList = start_dateTime, end_dateTime, summary
    #I want: event in eventList = start_dateTime, end_dateTime, summary, date, string that says start time to end time in humanized format
    for event in eventList:
        #get start_dateTime, turn it into date, append to event
        date = beautify_date(event[0])
        event.append(date)
        #beautify the begin time of the time block
        prettyBeginTime = beautify_time(event[0])
        prettyEndTime = beautify_time(event[1])
        string = str(prettyBeginTime) + " - " + str(prettyEndTime) + ": "
        event.append(string)
        event[0] = event[0].isoformat()
        event[1] = event[1].isoformat()
    for event in eventList:
        print(event)
    return eventList

#I got the psuedocode for this function from Sam Champer because he's awesome
#he knows that i used the function
#he's ok with it
def crop(listOfTimes, minTime):
    newList = []
    for block in listOfTimes:
        if block[0].shift(minutes=+minTime) <= block[1]:
            newList.append(block)
    return newList

def beautify_date(date):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

def beautify_time(time):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"