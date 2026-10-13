import network   # Handles the wifi connection
import ownSQL
import time

### To Do: Fill in your wifi connection data and change the server data
ssid = 'ssid'
password = 'secret'


### To Do: Fill in your server connection data
db_host = '127.0.0.1'
db_user = 'root'
db_password = '123456'

# Connect to network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

while not wlan.isconnected():
    print("Wifi Status: ", wlan.status())
    time.sleep(1)

print("Wifi connected")

try:
    ownSQL.create_database(
        host=db_host, user=db_user, password=db_password, database='createDropDatabaseTest'
    )
    print("CREATE DATABASE ok")
    
    try:
        ownSQL.drop_database(
            host=db_host, user=db_user, password=db_password, database='createDropDatabaseTest'
        )
        print("DROP DATABASE ok")

    except Exception:
        print("DROP DATABASE failed")
    
except Exception:
    print("CREATE DATABASE failed")