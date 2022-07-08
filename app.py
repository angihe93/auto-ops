import os
import psycopg2
from flask import Flask, render_template, request
import bcrypt

app = Flask(__name__)

host = os.environ.get('DB_HOST')
database = os.environ.get('DB_DB')
user = os.environ.get('DB_USER')
password = os.environ.get('DB_PW')

def get_db_connection():
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password)
    return conn


@app.route('/', methods =["GET", "POST"])
def gfg():
    if request.method == "POST":
        key = request.form.get("key")
        if bcrypt.checkpw(bytes(key,encoding='utf-8'),b'$2b$12$h4LsLf0upvAPCiKTZFnxnOj25gp9OTmeRtca3y8eULezXvdlF3O1C'):
            conn = get_db_connection()
            cur = conn.cursor()
            # cur.execute('SELECT * FROM orders;')
            cur.execute('''select orders.res_date_start, lower(replace(users.name,',',' ')), users.email, profiles.phone, users.address_num || ' ' || users.address_street || ' ' || users.address_apt || ' ' || users. address_zip as address,
                        reservations.charge, reservations.deposit, reservations.tax,
                        '(' || items.id || ') ' || items.name, orders.res_date_end,
                        reservations.is_extended
                        from orders
                        inner join reservations on orders.renter_id=reservations.renter_id and orders.item_id=reservations.item_id and orders.res_date_start = reservations.date_started and orders.res_date_end = reservations.date_ended
                        inner join items on items.id=orders.item_id
                        inner join users on users.id=orders.renter_id
                        inner join profiles on profiles.id=users.id
                        order by orders.res_date_start, users.name''')
            # orders = cur.fetchall()
            rows = cur.fetchall()
            # print('orders',orders)
            # orders=cur.fetchone()
            cur.close()
            conn.close()
            return render_template('index.html', rows=rows)
            # return render_template("index.html")
    return render_template("key.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
