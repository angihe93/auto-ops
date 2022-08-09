from flask import Blueprint, request, session, redirect

from datetime import datetime, timedelta
from collections import defaultdict

import googleapiclient

from src.utils import get_db_connection

bp = Blueprint("calendar", __name__)

# @app.route('/makecalevents/<ltype>', methods =["GET", "POST"])
# def makecalevents(ltype): # include this in return of oauth2callback
@bp.route('/makecalevents', methods =["GET", "POST"])
def makecalevents():
    if 'credentials' not in session: return redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials( **session['credentials'] )

    service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)

    # from db get items for the same user with the same set pickup/dropoff datetime
    # join orders and logistics and reservations, get item names, links, prices
    # or get items in same event from rows, event_li, logi_li from gfg

    ltype = request.args.get('ltype')
    renter = request.args.get('renter')
    rid = request.args.get('rid')
    date = request.args.get('date')
    time = request.args.get('time')
    iname = request.args.get('item_name')
    ilink = request.args.get('item_link')
    tid = request.args.get('tid')
    address = request.args.get("address")
    phone = request.args.get("phone")
    payment = request.args.get("payment")
    notes = request.args.get("notes")
    email = request.args.get("email")

    tlink = 'https://admin.hubbub.shop/task/'+ltype+'/id='+tid

    ### check in db if there are other items being pickedup/dropped off for the same user at the same time

    conn = get_db_connection()
    cur = conn.cursor()

    if ltype=='dropoff':
        items_in_dropoff_query = """
            select distinct reservations.item_id, items.name,
            round( CAST(reservations.charge as numeric), 2),
            round( CAST(reservations.deposit as numeric), 2), round( CAST(reservations.tax as numeric), 2)
            from order_dropoffs
            inner join logistics on logistics.dt_sched=order_dropoffs.dt_sched and logistics.renter_id=order_dropoffs.renter_id
            inner join reservations on order_dropoffs.dropoff_date=reservations.date_started and order_dropoffs.renter_id=reservations.renter_id
            inner join items on reservations.item_id=items.id
            where reservations.is_calendared=TRUE and order_dropoffs.renter_id=%s and order_dropoffs.dropoff_date='%s' and logistics.chosen_time='%s'
        """%(rid,date,time)
        cur.execute(items_in_dropoff_query)
        rows = cur.fetchall()
        print('items in dropoff rows:',rows[-10:])

    elif ltype=='pickup':
        ### need to handle extensions!! order_pickups show post extension dates, but reservations.date_ended might not and the date associated with pickup time is the unextended date
        ### add extended dates in pickup date time columns?
        p_date=request.args.get("p_date")
        items_in_pickup_query = """
            select distinct reservations.item_id, items.name,
            round( CAST(reservations.charge as numeric), 2),
            round( CAST(reservations.deposit as numeric), 2), round( CAST(reservations.tax as numeric), 2)
            from order_pickups
            inner join logistics on logistics.dt_sched=order_pickups.dt_sched and logistics.renter_id=order_pickups.renter_id
            inner join reservations on order_pickups.pickup_date=reservations.date_ended and order_pickups.renter_id=reservations.renter_id
            inner join items on reservations.item_id=items.id
            where reservations.is_calendared=TRUE and order_pickups.renter_id=%s and order_pickups.pickup_date='%s' and logistics.chosen_time='%s'
        """%(rid,p_date,time)
        cur.execute(items_in_pickup_query)
        rows = cur.fetchall()
        print('items in pickup rows:',rows[-10:])

    cur.close()
    conn.close()

    ## user notes
    ## user email (to put in body or as attendee)
    print('date:',date)
    print('time:',time)
    # print('iname',iname)
    # print('ilink:',ilink)
    # put all items in same pickup/dropoff in a list
    # if len(rows)==1:
    iid_li=[i[0] for i in rows]
    iname_li=[i[1] for i in rows]
    ilink_li=['https://www.hubbub.shop/inventory/i/id='+str(i[0]) for i in rows]

    ### accurate for dropoffs only, if no extension is made before dropoff:
    charge_li=[i[2] for i in rows]  # extension charges not included
    deposit_li=[i[3] for i in rows] # extension deposits not included
    tax_li=[i[4] for i in rows] # extension taxes not included
    total = sum(charge_li)+sum(deposit_li)+sum(tax_li)
    print('iid_li',iid_li)
    print('iname_li',iname_li)
    print('ilink_li',ilink_li)
    print('charge_li',charge_li)
    print('deposit_li',deposit_li)
    print('tax_li',tax_li)
    print('total',total)
    print('tid:',tid)
    print('address:',address)
    print('phone:',phone)
    print('payment:',payment)

    if ltype=='dropoff':
        start_time_dt=datetime.strptime(date+' '+time,'%Y-%m-%d %H:%M:%S')
        start_time_str=date+'T'+time
    elif ltype=='pickup':
        start_time_dt=datetime.strptime(p_date+' '+time,'%Y-%m-%d %H:%M:%S')
        start_time_str=p_date+'T'+time

    print('start_time_dt',start_time_dt)
    print('start_time_str',start_time_str)

    end_time_dt=start_time_dt + timedelta(hours=1)
    end_time_str=end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str=end_time_str.replace(' ','T')
    end_time_dt_user=start_time_dt + timedelta(minutes=15)
    end_time_str_user=end_time_dt_user.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str_user=end_time_str_user.replace(' ','T')

    print('end_time_dt',end_time_dt)
    print('end_time_str',end_time_str)
    print('email',email)
    print('notes',notes)

    items_html_ops="<ul>"
    for i in range(len(iname_li)):
        items_html_ops+= ("<li>"+"<a href=%s>(%s) %s</a>"%(ilink_li[i],iid_li[i],iname_li[i])+"</li>")
    items_html_ops+="</ul>"

    items_html_user="<ul>"
    for i in range(len(iname_li)):
        items_html_user+= ("<li>"+"<a href=%s>%s</a>"%(ilink_li[i],iname_li[i])+"</li>")
    items_html_user+="</ul>"

    if ltype=='dropoff':

        df_event_ops = {
            'summary': renter.split(" ")[0].capitalize()+" "+renter.split(" ")[1].capitalize()+ ' '+ltype.capitalize(),
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str,'timeZone':'America/New_York',}, # end_time_str
            'description': """%s \n\nItems:%sTotal $%s from %s\n\nUser notes: %s\n\nUser phone: %s
             """%(tlink,items_html_ops,total,payment,notes,phone),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
            }
        print('df_event_ops',df_event_ops)


        summary = renter.split(" ")[0].capitalize()
        if len(rows)>1:
            summary+=" Items"
        else:
            summary+=" Item"
        summary+=" Drop-off"

        df_event_user = {
            'summary': summary,
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str_user,'timeZone':'America/New_York',}, # end_time_str
            'description': """Our Hub-Bud ___ will be dropping off the following:\n%sTotal due at drop-off: $%s \n\nPlease be prompt. Failure to show up after 30 minutes will result in a $5 drop-off attempt charge and a forfeit of guarantee of rental of the item(s).
             """%(items_html_user,total),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
        }

        ops_event = service.events().insert(calendarId='c_puitor2pblvjgid67mj32m6em0@group.calendar.google.com', body=df_event_ops).execute()
        user_event = service.events().insert(calendarId='c_puitor2pblvjgid67mj32m6em0@group.calendar.google.com', body=df_event_user).execute()

    elif ltype=='pickup':

        pu_event_ops = {
            'summary': renter.split(" ")[0].capitalize()+" "+renter.split(" ")[1].capitalize()+ ' '+ltype.capitalize(),
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str,'timeZone':'America/New_York',}, # end_time_str
            'description': """%s \n\nItems:%sUser notes: %s\n\nUser phone: %s
             """%(tlink,items_html_ops,notes,phone),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
        }
        print('pu_event_ops',pu_event_ops)


        summary = renter.split(" ")[0].capitalize()
        if len(rows)>1:
            summary+=" Items"
        else:
            summary+=" Item"
        summary+=" Pick-up"

        pu_event_user = {
            'summary': summary,
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str_user,'timeZone':'America/New_York',}, # end_time_str
            'description': """Our Hub-Bud ___ will be picking up the following:\n%sPlease be prompt. Failure to show up after 30 minutes will result in a $5 pickup attempt charge. Please make sure each item is in a clean and usable state upon pickup, charges may be applied otherwise.\n(For mini-fridges, it is recommended to unplug and defrost them at least 24 hours before pick-up)
             """%(items_html_user),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
        }

        ops_event = service.events().insert(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', body=pu_event_ops).execute()
        user_event = service.events().insert(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', body=pu_event_user).execute()

    # print('Event created: %s' % (event.get('htmlLink')))

    return """ops event created at <a href=%s>%s </a>, user event created at <a href=%s>%s </a>, double check for correctness and add attendees"""%(ops_event.get('htmlLink'),ops_event.get('htmlLink'),user_event.get('htmlLink'),user_event.get('htmlLink'))


@bp.route('/calendar')
def calendar():
    if 'credentials' not in session: return redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials( **session['credentials'] )

    try:
        service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
        print('service built')
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com',
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        print('events_result',events_result)
        # return flask.redirect('mainsiteops')
        # events = events_result.get('items', [])
    except:
        print("exception when accessing events in mainsiteops")
        return """
        please login with valid email<br>
        <a href="clear">clear credentials and try again</a>
        """

    month_dict = {'01':['Jan',31],'02':['Feb',28],'03':['Mar',31],'04':['Apr',30],'05':['May',31],'06':['Jun',30],
                  '07':['Jul',31],'08':['Aug',31],'09':['Sep',30],'10':['Oct',31],'11':['Nov',30],'12':['Dec',31]}

    zipcode_dict=defaultdict(lambda:"other")
    zipcode_dict['10027']='CU'
    zipcode_dict['10025']='CU'
    zipcode_dict['10012']='NYU'
    zipcode_dict['10003']='NYU'
    zipcode_dict['10014']='NYU'
    zipcode_dict['10011']='NYU'
    # zipcode_dict = {'10027':'CU','10025':'CU'}

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        select orders.id, cast(orders.res_date_start as varchar),
        '(' || items.id || ') ' || items.name, users.email,
        users.address_zip, logistics.address_zip, coalesce(cast(logistics.timeslots as varchar),''), coalesce(cast(logistics.chosen_time as varchar),''),
        'dropoff'
        from orders
        inner join items on items.id=orders.item_id
        inner join users on users.id=orders.renter_id
        left join order_dropoffs on orders.id=order_dropoffs.order_id
        left join logistics on logistics.dt_sched=order_dropoffs.dt_sched
        where res_date_start>'2022-08-01'
        order by res_date_start,email
    """)
    dropoff_rows=cur.fetchall()
    dropoff_rows = [list(i) for i in dropoff_rows]
    print("dropoff_rows")
    print(dropoff_rows)
    print("\n\n\n")


    cur.execute("""
        select orders.id, cast(orders.res_date_end as varchar),
        '(' || items.id || ') ' || items.name, users.email,
        users.address_zip, logistics.address_zip, coalesce(cast(logistics.timeslots as varchar),''), coalesce(cast(logistics.chosen_time as varchar),''),
        'pickup'
        from orders
        inner join items on items.id=orders.item_id
        inner join users on users.id=orders.renter_id
        left join order_pickups on orders.id=order_pickups.order_id
        left join logistics on logistics.dt_sched=order_pickups.dt_sched
        where res_date_end>'2022-08-01'
        order by res_date_end,email
    """)
    pickup_rows=cur.fetchall()
    pickup_rows = [list(i) for i in pickup_rows]
    print("pickup_rows")
    print(pickup_rows)
    print("\n\n\n")
    # check for extensions

    cur.execute("select extensions.order_id, cast(extensions.res_date_start as varchar), cast(extensions.res_date_end as varchar) from extensions")
    extensions=cur.fetchall()
    # ext_li=[] # holds the date that go in pickup datetime
    for i in pickup_rows:
        # if order number is in extensions, add extension values, else, add none
        e = [e[2] for e in extensions if e[0]==i[0]]
        if len(e)>0:
            # if multiple extensions on same item/order, multiple rows in extensions with same order id but res dates are changed
            # sort e by res_date_end, take the latest res_date_end
            e.sort()
            # ext_li.append(e[-1])
            i[1]=e[-1]
        # else:
        #     ext_li.append(i[3])
    print("pickup rows after extension check:")
    print(pickup_rows)

    ### rentals that end before 8/1 but have extensions that end after 8/1 ###
    # new query, change where to res_date_end<'2022-08-01' and extensions.res_date_end>'2022-08-01'
    cur.execute("""
        select orders.id, subquery.res_date_end,
        '(' || items.id || ') ' || items.name, users.email,
        users.address_zip, logistics.address_zip, coalesce(cast(logistics.timeslots as varchar),''), coalesce(cast(logistics.chosen_time as varchar),''),
        'pickup'
        from
        orders inner join
            (select extensions.order_id, cast(max(extensions.res_date_end) as varchar) as res_date_end
            from orders
            inner join extensions on orders.id=extensions.order_id
            where orders.res_date_end<'2022-08-01' and cast(extensions.res_date_end as varchar) > '2022-08-01'
            group by extensions.order_id) as subquery
        on orders.id=subquery.order_id
        inner join items on items.id=orders.item_id
        inner join users on users.id=orders.renter_id
        left join order_pickups on orders.id=order_pickups.order_id
        left join logistics on logistics.dt_sched=order_pickups.dt_sched
        order by res_date_end,email
    """)
    pickup_rows_ext=cur.fetchall()
    pickup_rows_ext = [list(i) for i in pickup_rows_ext]
    print("pickup_rows_ext")
    print(pickup_rows_ext)
    print("\n\n\n")

    pickup_rows.extend(pickup_rows_ext)

    print("pickup rows after extension check and adding pickup_rows_ext:")
    print(pickup_rows)
    print("\n\n\n")

    # make table starting august
    # for each month, first row is month name, next row is days (sun-sat), then it's dates and logistics data alternating
    # while there are logistics events: while current date < last logistics event on file
    html="""
        <style type="text/css">
          body {
            font-family: calibri;}
        </style>
        <a href="mainsiteops">Main site Ops view</a>
        <ul>
        <li>each entry starts with the task type (pickup or dropoff), location (CU or NYU), and time (precise time if Ops has scheduled a time, timeslots if user has submitted availability but Ops has not scheduled a time, empty if user has not submitted availability)</li>
        <li>location is CU if the zipcode on dropoff/pickup form (or the zipcode on file, if user has not filled out the form) is 10025 or 10027. location is NYU if the zipcode is one of the following: 10003, 10011, 10012, 10014. location is other if the zipcode is different from any of the above</li>
        </ul>
        <table>
          <tr>
            <th>Aug 2022</th>
            <th> </th>
            <th> </th>
            <th> </th>
            <th> </th>
            <th> </th>
            <th> </th>
          </tr>
         """
    all_events=dropoff_rows
    all_events.extend(pickup_rows)
    all_events=sorted(all_events, key=lambda x: (x[1],x[3],x[7],x[6])) # sort by date, email, time chosen, timeslots, empty times are first, then ascending
    print("\n\n\n")
    print("all_events")
    print(all_events)

    # make pandas df, order by date, combine orders for the same user of same type on same day (at same time?)
    # or do that without pandas? in a for loop, then sort list https://stackoverflow.com/questions/36955553/sorting-list-of-lists-by-the-first-element-of-each-sub-list
    prev_email=all_events[0][3]
    prev_type=all_events[0][-1]
    prev_day=all_events[0][1]
    i=1
    length=len(all_events)
    while i<length:
        # print('i',i)
        # print('prev email',prev_email)
        # print('prev type',prev_type)
        # print('prev_day',prev_day)
        # print('current email',all_events[i][3])
        # print('current type',all_events[i][-1])
        # print('current item',all_events[i][2])
        # length=len(all_events) #??
        if all_events[i][3]==prev_email and all_events[i][-1]==prev_type and all_events[i][1]==prev_day:
            # print('email, task type, and date = last one')
            prev_email=all_events[i][3]
            prev_type=all_events[i][-1]
            prev_day=all_events[i][1]
            all_events[i-1][2]+=', '+all_events[i][2] # append current item
            del all_events[i]
        elif all_events[i][3]!=prev_email or all_events[i][-1]!=prev_type or all_events[i][1]!=prev_day:
            # print('email, task type, or date != last one')
            prev_email=all_events[i][3]
            prev_type=all_events[i][-1]
            prev_day=all_events[i][1]
            i+=1
        length=len(all_events) #??
        # print('new length',length)
        # prev_email=all_events[i][3]
        # prev_type=all_events[i][-1]
        # i+=1
    print("\n\n\n")
    print("all_events_after mod:")
    print(all_events)

    # iterate through all upcoming dates, for each date output the events with that date
    upcoming_dates=sorted(list(set([i[1] for i in all_events])))
    # print('upcoming_dates',upcoming_dates)
    curr_year = '2022'
    curr_month = '08'
    curr_mo_index = 7
    months = ['01','02','03','04','05','06','07','08','09','10','11','12']
    years = ['2022','2023','2024','2025']
    # while i<=31:
    ## generate rows of dates of size 7, iterate through each row, add event data as needed
    date_rows=[[' ','1','2','3','4','5','6']]
    i=7
    while i<=31:
        date_rows.append([*range(i,min(31+1,i+7))])
        i+=7
    # for last entry in date_rows, count how many there are, append empties as needed
    if len(date_rows[-1])<7:
        date_rows[-1].extend([' ']*(7-len(date_rows[-1])))
    print(date_rows)

    # make dictionary of date:events ?
    # iterate through date_rows, add corresponding events to each day?
    # date_events_dict shows a list of lists for each date
    date_events_dict=defaultdict(lambda:[])
    for e in all_events:
        event_date=e[1]
        try:# if date exists
            date_events_dict[event_date].append(e)
        except:
            date_events_dict[event_date]=e
    print("\n\n\n")
    print('date_events_dict')
    print(date_events_dict)

    html+="""
        <tr>
          <th>Sun</th>
          <th>Mon</th>
          <th>Tue</th>
          <th>Wed</th>
          <th>Thu</th>
          <th>Fri</th>
          <th>Sat</th>
        </tr>

    """
    # <table>
    ######## new  ########
    print("\n\n\n")
    # remove each event entry after its added to html
    # while date_events_dict: # while there are entries in date_events_dict
    # while curr_mo_index < len(months) :
    while date_events_dict:
        event_rows=[]
        curr_month = months[curr_mo_index]
        print('curr_month',curr_month)
        curr_mo_date_events_dict=dict(filter(lambda i:i[0][5:7]==curr_month and i[0][:4]==curr_year,date_events_dict.items()))

        #### generate date_rows ####
        if curr_month=='08' and curr_year=='2022': # use the pregenerated one
            date_rows=date_rows
        else:
            html+="""
            <tr>
            <td> </td>
            </tr>
            <tr>
              <th>%s</th>
              <th> </th>
              <th> </th>
              <th> </th>
              <th> </th>
              <th> </th>
              <th> </th>
            </tr>
            """%(month_dict[curr_month][0]+" "+curr_year)
            html+="""
                <tr>
                  <th>Sun</th>
                  <th>Mon</th>
                  <th>Tue</th>
                  <th>Wed</th>
                  <th>Thu</th>
                  <th>Fri</th>
                  <th>Sat</th>
                </tr>
            """
            # see previous date_rows to see where 01 should start
            max_day=month_dict[curr_month][1]
            print('max day',max_day)
            start_position=len([i for i in date_rows[-1] if i!=' '])
            # generate first line
            if start_position==7:
                start_position=0
                date_rows=[[]]
            else:
                date_rows=[[' ']*start_position]
            date_rows[0].extend([*range(1,7-start_position+1)])
            print('first row of date_rows',date_rows)
            # generate the rest
            i=int(date_rows[0][-1])+1 # value to start with for next row
            print('i,value to start with for next row',i)
            while i<=max_day:
                date_rows.append([*range(i,min(max_day+1,i+7))])
                i+=7
            # for last entry in date_rows, count how many there are, append empties as needed
            if len(date_rows[-1])<7:
                date_rows[-1].extend([' ']*(7-len(date_rows[-1])))
            print(date_rows)

        for d in date_rows:
            html+="<tr>"
            for i in d:
                html+="<th>"+str(i)+"</th>"
            html+="</tr>"
            curr_event_row=[]
            html+="<tr>"
            for date in d:
                curr_date=curr_year+'-'+curr_month+'-'+str(date) if len(str(date))==2 else curr_year+'-'+curr_month+'-0'+str(date)
                # print('curr_date',curr_date)
                try:
                    event_data="<td>"
                    curr_date_events_sorted=sorted(curr_mo_date_events_dict[curr_date], key=lambda x: (x[7],x[6])) # sort events in a day by chosen time, then timeslots
                    for i in curr_date_events_sorted: # for each event in curr_date
                        # print('i',i)
                        event_data_time = i[7] # if chosen time exists, use that, else use timeslots
                        if event_data_time=="":
                            event_data_time=i[6]
                        event_data_zipcode=i[5]
                        if not event_data_zipcode: # if zipcode in logistics form exists, use that, else use zipcode in account
                            event_data_zipcode=i[4]
                        event_data_location = zipcode_dict[event_data_zipcode]
                        event_data+="<b>"+i[-1]+", "+event_data_location+", "+event_data_time+":</b> "+i[2]+"<br>"

                    event_data+="</td>"
                    # print('event_data in try:',event_data)

                    html+=event_data
                    print('date_events_dict date entry to delete:',date_events_dict[curr_date])
                    del date_events_dict[curr_date]
                    print('date_events_dict after deletion:')
                    print(date_events_dict)
                    # html+="<td>"+str(curr_mo_date_events_dict[curr_date])+"</td>"
                    # curr_event_row.append(curr_mo_date_events_dict[curr_date])
                except Exception as e:
                    # print(e)
                    # print('except')
                    html+="<td></td>"
                    # curr_event_row.append([])
                # print('curr_event_row',curr_event_row)
                # del date_events_dict[date]
            html+="</tr>"
            event_rows.append(curr_event_row)
            print('event_rows',event_rows)
            print("\n")


        if curr_mo_index==len(months)-1: # at last month, or months[11]='12'
            curr_mo_index=0 # reset to months[0]
            curr_year = str(int(curr_year)+1)
        else:
            curr_mo_index+=1

    html+="</table>"

    # if date is in current month, proceed to add date numbers and corresponding events on each date
    # if date is in next month, add month header, then sat-sun row, then add date numbers and corresponding events

    return html
    # return(render_template('calendar.html'))
