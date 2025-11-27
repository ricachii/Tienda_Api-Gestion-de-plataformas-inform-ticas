import os
import mysql.connector
conn = mysql.connector.connect(host='192.168.56.20', user='rikashii', password='Lulita2014', database='tienda')
cur = conn.cursor()
cur.execute("select id,email,HEX(password_hash),HEX(salt) from usuarios where email=%s", ('nricciardi2021@udec.cl',))
print(cur.fetchone())
cur.close()
conn.close()
