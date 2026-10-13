# ownSQL

**A MySQL database driver for MicroPython, supporting MySQL Server 8.x and 9.x.**

ownSQL was derived from `micropg_lite` and adapted from PostgreSQL to MySQL with the assistance of AI tools. `micropg`, the original project on which `micropg_lite` is based, was developed by [Hajime Nakagami](https://github.com/nakagami). Many thanks for the great work — without `micropg`, `ownSQL` would not exist!

For support, questions, or suggestions, please [open an issue](https://github.com/TimonW-Dev/ownSQL/issues) or contact me by email using the address linked in [my profile](https://github.com/TimonW-Dev). Pull requests are welcome. This is a voluntary open-source project, so support is provided as time allows.


## 📥 Installation

### Choose a file

We recommend [`ownSQL.py`](https://github.com/TimonW-Dev/ownSQL/blob/main/ownSQL.py). If you want to save RAM, you can use the precompiled [`ownSQL.mpy`](https://github.com/TimonW-Dev/ownSQL/blob/main/ownSQL.mpy) file. For most projects, the `.py` file is sufficient. The `.mpy` file may not be compatible with every MicroPython firmware version and is not as easy to edit or debug.

### Install on your microcontroller

1. Download the [ownSQL.py](https://github.com/TimonW-Dev/ownSQL/blob/main/ownSQL.py) file from this [repository](https://github.com/TimonW-Dev/ownSQL) to your local computer.
2. Copy it to the `/lib` folder on your microcontroller using Thonny IDE or another file transfer tool. Create the folder if it does not exist.
   - **Thonny tip:** Open **View** in the top bar and enable **Files** to upload files and create folders on the microcontroller.
3. Import the library in your MicroPython script. The import name is the same for both file formats:

```python
import ownSQL
```

The files on your microcontroller should be arranged like this:

```text
/
|- example.py
|- lib/
    |- ownSQL.py
```

## 🚀 Examples

Establish a network connection before running `ownSQL` code. The SELECT example below includes a Wi-Fi connection template; the other examples assume that the connection is already established.

The [`examples/` folder](https://github.com/TimonW-Dev/ownSQL/tree/main/examples) contains:

- [`docker-full-testing-container-setup`](https://github.com/TimonW-Dev/ownSQL/blob/main/examples/docker-full-testing-container-setup), to create an empty MySQL container.
- [`exampleDatabase.sql`](https://github.com/TimonW-Dev/ownSQL/blob/main/examples/exampleDatabase.sql), the database used by the examples.
- Complete test scripts with WLAN connection templates, plus examples for creating and dropping tables and databases.

### 🔍 SELECT (including Wi-Fi setup)

Replace the Wi-Fi credentials and server details with your own:

```python
import ownSQL
import network
import time

ssid = 'wifissid'
password = 'secret'

# Connect to the network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

while not wlan.isconnected():
    print("Wi-Fi status:", wlan.status())
    time.sleep(1)

print("Wi-Fi connected")

conn = ownSQL.connect(host='127.0.0.1', # Replace with your server's IP address
                    user='root',
                    password='123456',
                    database='exampledatabase')
cur = conn.cursor()

cur.execute('select * from customers')
selectresult = cur.fetchall()
conn.close()

# Print the raw data
print(selectresult)

# Print the data as rows
for row in selectresult:
    for value in row:
        print(value, end="\t")
    print()
```

### ➕ INSERT

```python
conn = ownSQL.connect(
    host='127.0.0.1',  # Replace with your server's IP address
    user='root',
    password='123456',
    database='exampledatabase'
)
cur = conn.cursor()

cur.execute(
    'INSERT INTO customers (id, firstName, lastName, email) values (%s, %s, %s, %s)',
    ['5', 'David', 'Wilson', 'david.wilson@example.com']
)
conn.commit()
conn.close()
```

### ✏️ UPDATE

```python
conn = ownSQL.connect(
    host='127.0.0.1',  # Replace with your server's IP address
    user='root',
    password='123456',
    database='exampledatabase'
)
cur = conn.cursor()

cur.execute("update customers set firstName='UpdatedFirstName' where id=2;")
conn.commit()
conn.close()
```

### 🗑️ DELETE

```python
conn = ownSQL.connect(
    host='127.0.0.1',  # Replace with your server's IP address
    user='root',
    password='123456',
    database='exampledatabase'
)
cur = conn.cursor()

cur.execute("delete from customers where id=1;")
conn.commit()
conn.close()
```