from flask import Blueprint, redirect, session

import googleapiclient

from google.oauth2.credentials import Credentials

bp = Blueprint("main", __name__)

@bp.route('/',)
def index():
    if 'credentials' not in session:
        return redirect('authorize')

    # Load credentials from the session.
    credentials = Credentials( **session['credentials'] )
    print('credentials loaded from session')

    # try:
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
    print('service built')

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    # print('Getting the upcoming 10 events')
    try:
        events_result = service.events().list(
            calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com',
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        print('events_result',events_result)
        return redirect('mainsiteops')
        # events = events_result.get('items', [])
    except:
        print("exception when accessing events in index()")
        # return "please login with valid email"
        return """
        please login with valid email<br>
        <a href="clear">clear credentials and try again</a>
        """

@bp.route('/mainsiteops', methods =["GET", "POST"])
def mainsiteops():
    if 'credentials' not in session: return redirect('authorize')

    # Load credentials from the session.
    credentials = Credentials( **session['credentials'] )
    print('credentials loaded from session')

    try:
        service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
        print('service built')
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
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
        # return "please login with valid email"
        return """
        please login with valid email<br>
        <a href="clear">clear credentials and try again</a>
        """

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''select cast(orders.res_date_start as varchar), lower(replace(users.name,',',' ')), users.email, profiles.phone, users.address_num || ' ' || users.address_street || ', ' || users.address_apt || ', NY ' || users. address_zip as address,
                '$' || cast(round( CAST(reservations.charge as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.deposit as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.tax as numeric), 2) as varchar),
                '(' || items.id || ') ' || items.name, cast(orders.res_date_end as varchar),
                reservations.is_extended, 'https://www.hubbub.shop/inventory/i/id=' || cast(items.id as varchar), '@' || users.payment,
                orders.id, orders.renter_id, order_dropoffs.dt_sched, order_dropoffs.dt_completed, order_pickups.dt_sched, order_pickups.dt_completed,
                reservations.dt_created
                from orders
                inner join reservations on orders.renter_id=reservations.renter_id and orders.item_id=reservations.item_id and orders.res_date_start = reservations.date_started and orders.res_date_end = reservations.date_ended
                inner join items on items.id=orders.item_id
                inner join users on users.id=orders.renter_id
                inner join profiles on profiles.id=users.id
                left join order_dropoffs on orders.id=order_dropoffs.order_id
                left join order_pickups on orders.id=order_pickups.order_id
                order by orders.res_date_start, users.email, reservations.dt_created''')

    rows = cur.fetchall()
    print('rows:',rows[-5:])
    # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
    # rows to main site ops columns mapping
    # i[0]: rental start
    # i[1]: customer name
    # i[2]: customer email
    # i[3]: customer phone
    # i[4]: customer location
    # i[5]: sub price
    # i[6]: deposit
    # i[7]: tax
    # i[8]: item id and name
    # i[9]: res date end
    # i[10]: is extended
    # i[11]: item link
    # i[12]: payment
    # i[13]: order id
    # i[14]: renter id
    # i[15]: order_dropoffs.dt_sched
    # i[16]: order_dropoffs.dt_completed
    # i[17]: order_pickups.dt_sched
    # i[18]: order_pickups.dt_completed
    # i[19]: reservations.dt_created

    event_li = []
    for i in rows:
        if type(i[15])!=type(None) and type(i[16])==type(None) and type(i[17])!=type(None) and type(i[18])==type(None): # both dropoff and pickup needs events
            event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],1,1)) # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
        elif type(i[15])!=type(None) and type(i[16])==type(None) and type(i[17])==type(None) and type(i[18])==type(None): # only dropoff need event
            event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],1,0))
        elif type(i[15])!=type(None) and type(i[16])!=type(None) and type(i[17])!=type(None) and type(i[18])==type(None): # only pickup need event
            event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],0,1))
        else: # neither needs event yet
            event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],0,0))

    cur.execute("select * from logistics")
    logistics = cur.fetchall()

    logi_li = [] # everything in event_li except dt_sched, plus chosen time, address, notes for pick up and dropoff
    # res date start, res date end, order id, renter id, 1 if dropoff needs event, 1 if pickup needs event
    # add logistics data, where either dropoff needs event or pickup needs event, add the corresponding logistics row
    for i in event_li:
        if i[-2]==1 and i[-1]==0: # dropoff needs event
            # print('dropoff needs event')
            # join with logstics on dt_sched and renter_id, make sure dt_sched is from order_dropoffs
            dts = i[4]
            rid = i[3]
            logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
            #### if logi[-1] ie. chosen time is null, then append timeslots instead, and change link to the task id ###
            if type(logi[-1])==type(None):
                dropoff_time=logi[3] # show timeslots
                activate_makecalevents_url_dropoff=0
            else:
                dropoff_time=logi[-1]
                activate_makecalevents_url_dropoff=1
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],dropoff_time,str(logi[5])+' '+logi[6]+', '+logi[7]+', NY '+logi[8],logi[1],'','','',activate_makecalevents_url_dropoff,0))
            # print(logi)
        elif i[-1]==1 and i[-2]==0: # pickup needs event
            # print('pickup needs event')
            dts = i[5]
            rid = i[3]
            logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
            if type(logi[-1])==type(None):
                pickup_time=logi[3] # show timeslots
                activate_makecalevents_url_pickup=0
            else:
                pickup_time=logi[-1]
                activate_makecalevents_url_pickup=1
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','',pickup_time,str(logi[5])+' '+logi[6]+' '+logi[7]+' '+logi[8],logi[1],0,activate_makecalevents_url_pickup))
            # print(logi)
        elif i[-2]==1 and i[-1]==1: # both needs events
            # print('both need event')
            dts_d = i[4]
            dts_p = i[5]
            rid = i[3]
            logi_d = [l for l in logistics if l[0]==dts_d and l[4]==rid][0]
            logi_p = [l for l in logistics if l[0]==dts_p and l[4]==rid][0]
            if type(logi_d[-1])==type(None):
                dropoff_time=logi_d[3]
                activate_makecalevents_url_dropoff=0
            else:
                dropoff_time=logi_d[-1]
                activate_makecalevents_url_dropoff=1
            if type(logi_p[-1])==type(None):
                pickup_time=logi_p[3]
                activate_makecalevents_url_pickup=0
            else:
                pickup_time=logi_p[-1]
                activate_makecalevents_url_pickup=1
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],dropoff_time,str(logi_d[5])+' '+logi_d[6]+' '+logi_d[7]+' '+logi_d[8],logi_d[1],pickup_time,str(logi_p[5])+' '+logi_p[6]+' '+logi_p[7]+' '+logi_p[8],logi_p[1], activate_makecalevents_url_dropoff,activate_makecalevents_url_pickup))
        else: # neither needs event
            # print('else')
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','','','','',0,0))

    # check for extensions and prepend appropriate pickup dates to pickup datetime column
    cur.execute("select * from extensions")
    extensions=cur.fetchall()
    ext_li=[] # holds the date that go in pickup datetime
    for i in rows:
        # if order number is in extensions, add extension values, else, add none
        e = [e[4] for e in extensions if e[0]==i[13]]
        if len(e)>0:
            # if multiple extensions on same item/order, multiple rows in extensions with same order id but res dates are changed
            # sort e by res_date_end, take the latest res_date_end
            e.sort()
            ext_li.append(e[-1])
        else:
            ext_li.append(i[9])

    cur.close()
    conn.close()

    # list to store calendar info: dropoff/pickup type, renter name, rental start (for dropoff), rental end (for pickup), chosen time, items, total due/deposit return, task id from ops (id=order id), renter address, renter phone, renter payment
    # add it to session so makecalevents can access https://stackoverflow.com/questions/27611216/how-to-pass-a-variable-between-flask-pages

    return render_template('index.html', rows=rows, logi_li=logi_li, ext_li=ext_li) #, activate_makecalevents_url=activate_makecalevents_url)
            # # return render_template("index.html")
    # return render_template("key.html")
