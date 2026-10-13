#########################################################################################
# MIT License
# 
# Copyright (c) 2026 TimonW-Dev
# Copyright (c) 2014-2019, 2021-2026 Hajime Nakagami
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#########################################################################################
# ownSQL is a MySQL database driver for MicroPython, supporting MySQL Server 8.x and 9.x.
# It was derived from micropg_lite and adapted from PostgreSQL to MySQL with the
# assistance of AI tools. micropg, the original project on which micropg_lite is based,
# was developed by Hajime Nakagami.
#########################################################################################

import socket


CLIENT_LONG_PASSWORD = 0x00000001
CLIENT_LONG_FLAG = 0x00000004
CLIENT_CONNECT_WITH_DB = 0x00000008
CLIENT_PROTOCOL_41 = 0x00000200
CLIENT_SSL = 0x00000800
CLIENT_TRANSACTIONS = 0x00002000
CLIENT_SECURE_CONNECTION = 0x00008000
CLIENT_PLUGIN_AUTH = 0x00080000


class Error(Exception):
    pass


class OperationalError(Error):
    pass


class ProgrammingError(Error):
    pass


def _lost():
    raise OperationalError("MySQL: lost connection")


def _lenenc_int(data, pos=0):
    if pos >= len(data):
        raise OperationalError("MySQL: truncated length-encoded integer")
    first = data[pos]
    pos += 1
    if first < 0xfb:
        return first, pos
    if first == 0xfc:
        if len(data) < pos + 2:
            raise OperationalError("MySQL: truncated length-encoded integer")
        return int.from_bytes(data[pos:pos + 2], "little"), pos + 2
    if first == 0xfd:
        if len(data) < pos + 3:
            raise OperationalError("MySQL: truncated length-encoded integer")
        return int.from_bytes(data[pos:pos + 3], "little"), pos + 3
    if first == 0xfe:
        if len(data) < pos + 8:
            raise OperationalError("MySQL: truncated length-encoded integer")
        return int.from_bytes(data[pos:pos + 8], "little"), pos + 8
    if first == 0xfb:
        return None, pos
    raise OperationalError("MySQL: invalid length-encoded integer")


def _lenenc_bytes(data, pos=0):
    size, pos = _lenenc_int(data, pos)
    if size is None:
        return None, pos
    if size > len(data) - pos:
        raise OperationalError("MySQL: truncated length-encoded value")
    return data[pos:pos + size], pos + size


def _sha256(data):
    import hashlib
    return hashlib.sha256(data).digest()


def _auth_response(plugin, password, salt, tls_active=False):
    if plugin == "sha256_password":
        if not tls_active:
            raise OperationalError(
                "MySQL: sha256_password authentication requires use_ssl=True"
            )
        return password.encode("utf-8") + b"\x00"
    if not password:
        return b""
    raw_password = password.encode("utf-8")
    if plugin == "caching_sha2_password":
        stage1 = _sha256(raw_password)
        stage2 = _sha256(stage1)
        stage3 = _sha256(salt + stage2)
        return bytes(a ^ b for a, b in zip(stage1, stage3))
    if plugin == "mysql_native_password":
        import hashlib
        stage1 = hashlib.sha1(raw_password).digest()
        stage2 = hashlib.sha1(stage1).digest()
        stage3 = hashlib.sha1(salt + stage2).digest()
        return bytes(a ^ b for a, b in zip(stage1, stage3))
    raise OperationalError("MySQL: unsupported authentication plugin: " + plugin)


def _query_with_params(query, params):
    if not isinstance(params, (tuple, list)):
        raise ProgrammingError("MySQL parameters must be a tuple or list")

    result = []
    param_index = 0
    pos = 0
    while pos < len(query):
        char = query[pos]
        if char == "%" and pos + 1 < len(query):
            marker = query[pos + 1]
            if marker == "%":
                result.append("%")
                pos += 2
                continue
            if marker == "s":
                if param_index >= len(params):
                    raise ProgrammingError("not enough parameters for query")
                result.append(_sql_literal(params[param_index]))
                param_index += 1
                pos += 2
                continue
        result.append(char)
        pos += 1

    if param_index != len(params):
        raise ProgrammingError("too many parameters for query")
    return "".join(result)


def _sql_literal(value):
    if value is None:
        return "NULL"
    if value is True:
        return "1"
    if value is False:
        return "0"
    if isinstance(value, (int, float)):
        return str(value)
    import binascii
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        hex_value = binascii.hexlify(encoded).decode("ascii")
        return "CONVERT(X'" + hex_value + "' USING utf8mb4)"
    if isinstance(value, (bytes, bytearray)):
        hex_value = binascii.hexlify(bytes(value)).decode("ascii")
        return "X'" + hex_value + "'"
    raise ProgrammingError("unsupported MySQL parameter type: " + type(value).__name__)


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.rowcount = -1
        self.lastrowid = 0
        self._rows = []

    def execute(self, query, params=()):
        if not self.connection:
            raise OperationalError("MySQL: cursor is closed")
        if not isinstance(query, str):
            raise ProgrammingError("MySQL query must be a string")
        self.description = None
        self.rowcount = -1
        self.lastrowid = 0
        self._rows = []
        query = _query_with_params(query, params)
        self.connection.execute(query, self)
        return self

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows

    def close(self):
        self.connection = None
        self._rows = []


class connect:
    def __init__(self, host, user, password, database=None, port=3306, use_ssl=True):
        self.encoding = "utf-8"
        self.autocommit = False
        self.sock = None
        self.host = host
        self._password = password
        self._use_ssl = use_ssl
        self._tls_active = False
        self._seq = 0
        self._in_transaction = False

        sock = socket.socket()
        try:
            address = socket.getaddrinfo(host, port)[0][-1]
            sock.connect(address)
            self.sock = sock
            self._handshake(user, password, database)
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            self.sock = None
            raise

    def _read(self, size):
        sock = self.sock
        if not sock:
            _lost()
        result = b""
        while len(result) < size:
            read = sock.read if hasattr(sock, "read") else sock.recv
            chunk = read(size - len(result))
            if not chunk:
                _lost()
            result += chunk
        return result

    def _write(self, data):
        sock = self.sock
        if not sock:
            _lost()
        write = sock.write if hasattr(sock, "write") else sock.send
        view = memoryview(data)
        offset = 0
        while offset < len(data):
            written = write(view[offset:])
            if not written:
                _lost()
            offset += written

    def _read_packet(self):
        chunks = []
        while True:
            header = self._read(4)
            size = header[0] | (header[1] << 8) | (header[2] << 16)
            seq = header[3]
            if seq != self._seq:
                raise OperationalError("MySQL: invalid packet sequence")
            self._seq = (self._seq + 1) & 0xff
            chunks.append(self._read(size))
            if size < 0xffffff:
                return b"".join(chunks)

    def _send_packet(self, payload):
        offset = 0
        size = len(payload)
        while size - offset >= 0xffffff:
            part = payload[offset:offset + 0xffffff]
            self._write(bytes((0xff, 0xff, 0xff, self._seq)) + part)
            self._seq = (self._seq + 1) & 0xff
            offset += 0xffffff
        tail = payload[offset:]
        length = len(tail)
        header = bytes((length & 0xff, (length >> 8) & 0xff, (length >> 16) & 0xff, self._seq))
        self._write(header + tail)
        self._seq = (self._seq + 1) & 0xff

    def _handshake(self, user, password, database):
        greeting = self._read_packet()
        if greeting and greeting[0] == 0xff:
            self._server_error(greeting)
        if len(greeting) < 34 or greeting[0] != 10:
            raise OperationalError("MySQL: unsupported or malformed server greeting")

        pos = greeting.index(b"\x00", 1) + 1
        pos += 4
        salt = greeting[pos:pos + 8]
        pos += 9
        lower = int.from_bytes(greeting[pos:pos + 2], "little")
        pos += 2
        if pos >= len(greeting):
            raise OperationalError("MySQL: incomplete server greeting")
        pos += 1  # character set
        pos += 2  # status flags
        upper = int.from_bytes(greeting[pos:pos + 2], "little")
        pos += 2
        server_caps = lower | (upper << 16)

        auth_len = greeting[pos] if pos < len(greeting) else 0
        pos += 1 + 10
        if server_caps & CLIENT_SECURE_CONNECTION and pos < len(greeting):
            second_len = max(13, auth_len - 8) if auth_len else 13
            second_salt = greeting[pos:pos + second_len]
            if second_salt.endswith(b"\x00"):
                second_salt = second_salt[:-1]
            salt += second_salt
            pos += second_len
        plugin = "mysql_native_password"
        if server_caps & CLIENT_PLUGIN_AUTH and pos < len(greeting):
            plugin_end = greeting.find(b"\x00", pos)
            if plugin_end < 0:
                plugin_end = len(greeting)
            plugin = greeting[pos:plugin_end].decode("ascii")
        requested = (CLIENT_LONG_PASSWORD | CLIENT_LONG_FLAG | CLIENT_PROTOCOL_41 |
                     CLIENT_TRANSACTIONS | CLIENT_SECURE_CONNECTION |
                     CLIENT_PLUGIN_AUTH)
        if database:
            requested |= CLIENT_CONNECT_WITH_DB
        if self._use_ssl:
            requested |= CLIENT_SSL
        if not server_caps & CLIENT_PROTOCOL_41:
            raise OperationalError("MySQL: server does not support protocol 4.1")
        if not server_caps & CLIENT_SECURE_CONNECTION:
            raise OperationalError("MySQL: server does not support secure authentication")
        if not server_caps & CLIENT_PLUGIN_AUTH:
            raise OperationalError("MySQL: server does not support authentication plugins")
        client_caps = requested & server_caps
        if database and not client_caps & CLIENT_CONNECT_WITH_DB:
            raise OperationalError("MySQL: server does not support selecting a database at login")

        if self._use_ssl:
            if not server_caps & CLIENT_SSL:
                raise OperationalError("MySQL: server does not support TLS")
            self._seq = 1
            ssl_request = (client_caps.to_bytes(4, "little") +
                           (1024 * 1024).to_bytes(4, "little") +
                           b"\x2d" + bytes(23))
            self._send_packet(ssl_request)
            import ssl
            try:
                self.sock = ssl.wrap_socket(self.sock, server_hostname=self.host)
            except TypeError:
                self.sock = ssl.wrap_socket(self.sock)
            self._tls_active = True

        auth = _auth_response(plugin, password, salt, self._tls_active)
        response = (client_caps.to_bytes(4, "little") +
                    (1024 * 1024).to_bytes(4, "little") +
                    b"\x2d" + bytes(23) + user.encode("utf-8") + b"\x00" +
                    bytes((len(auth),)) + auth)
        if database:
            response += database.encode("utf-8") + b"\x00"
        response += plugin.encode("ascii") + b"\x00"
        self._send_packet(response)

        while True:
            packet = self._read_packet()
            if not packet:
                raise OperationalError("MySQL: empty authentication response")
            if packet[0] == 0x00:
                return
            if packet[0] == 0xff:
                self._server_error(packet)
            if packet[0] == 0xfe:
                end = packet.find(b"\x00", 1)
                if end < 0:
                    raise OperationalError("MySQL: malformed authentication switch")
                plugin = packet[1:end].decode("ascii")
                salt = packet[end + 1:]
                if salt.endswith(b"\x00"):
                    salt = salt[:-1]
                self._send_packet(
                    _auth_response(plugin, password, salt, self._tls_active)
                )
                continue
            if packet[0] == 0x01 and len(packet) > 1:
                if packet[1] == 0x03:
                    continue
                if packet[1] == 0x04:
                    if not self._tls_active:
                        raise OperationalError(
                            "MySQL: caching_sha2_password full authentication requires use_ssl=True"
                        )
                    self._send_packet(password.encode("utf-8") + b"\x00")
                    continue
            raise OperationalError("MySQL: unexpected authentication response")

    def _server_error(self, packet):
        code = int.from_bytes(packet[1:3], "little") if len(packet) >= 3 else 0
        pos = 3
        state = ""
        if len(packet) >= 9 and packet[3:4] == b"#":
            state = " " + packet[4:9].decode("ascii", "replace")
            pos = 9
        message = packet[pos:].decode(self.encoding, "replace")
        raise OperationalError("MySQL error %d%s: %s" % (code, state, message))

    def _read_ok(self, packet, cursor):
        pos = 1
        affected, pos = _lenenc_int(packet, pos)
        last_id, pos = _lenenc_int(packet, pos)
        if len(packet) >= pos + 4:
            status = int.from_bytes(packet[pos:pos + 2], "little")
            pos += 4  # status and warnings
        else:
            status = 0
        if cursor:
            cursor.description = None
            cursor.rowcount = affected if affected is not None else 0
            cursor.lastrowid = last_id if last_id is not None else 0
            cursor._rows = []
        return status

    def _column_definition(self, packet):
        pos = 0
        fields = []
        for _ in range(6):
            value, pos = _lenenc_bytes(packet, pos)
            fields.append(value)
        fixed_size, pos = _lenenc_int(packet, pos)
        if fixed_size is None or len(packet) < pos + fixed_size:
            raise OperationalError("MySQL: malformed column definition")
        charset = int.from_bytes(packet[pos:pos + 2], "little")
        length = int.from_bytes(packet[pos + 2:pos + 6], "little")
        column_type = packet[pos + 6]
        flags = int.from_bytes(packet[pos + 7:pos + 9], "little")
        name = fields[4].decode(self.encoding, "replace") if fields[4] else ""
        return (name, column_type, charset, flags, length)

    def _decode_value(self, value, column):
        if value is None:
            return None
        column_type, charset, flags = column[1], column[2], column[3]
        if column_type in (249, 250, 251, 252):
            return value if charset == 63 else value.decode(self.encoding, "replace")
        if column_type in (15, 253, 254) and (charset == 63 or flags & 0x80):
            return value
        text = value.decode(self.encoding, "replace")
        if column_type in (1, 2, 3, 8, 9, 13):
            try:
                return int(text)
            except ValueError:
                return text
        if column_type in (4, 5):
            try:
                return float(text)
            except ValueError:
                return text
        return text

    def _read_rows(self, columns, cursor):
        rows = []
        while True:
            packet = self._read_packet()
            if packet and packet[0] == 0xff:
                self._server_error(packet)
            if packet and packet[0] == 0xfe and len(packet) < 9:
                break
            if packet and packet[0] == 0xfb:
                raise OperationalError("MySQL: LOCAL INFILE is not supported")
            pos = 0
            row = []
            for column in columns:
                value, pos = _lenenc_bytes(packet, pos)
                row.append(self._decode_value(value, column))
            rows.append(tuple(row))
        if cursor:
            cursor._rows = rows
            cursor.description = [
                (column[0], column[1], None, column[4], None, None, None)
                for column in columns
            ]
            cursor.rowcount = len(rows)
            cursor.lastrowid = 0

    def _run_query(self, query, cursor):
        self._seq = 0
        self._send_packet(b"\x03" + query.encode(self.encoding))
        packet = self._read_packet()
        if packet and packet[0] == 0xff:
            self._server_error(packet)
        if packet and packet[0] == 0x00:
            self._read_ok(packet, cursor)
            return
        if packet and packet[0] == 0xfb:
            raise OperationalError("MySQL: LOCAL INFILE is not supported")
        column_count, _ = _lenenc_int(packet)
        if column_count is None:
            raise OperationalError("MySQL: malformed result set")
        columns = []
        for _ in range(column_count):
            definition = self._read_packet()
            if definition and definition[0] == 0xff:
                self._server_error(definition)
            columns.append(self._column_definition(definition))
        terminator = self._read_packet()
        if terminator and terminator[0] == 0xff:
            self._server_error(terminator)
        self._read_rows(columns, cursor)

    def cursor(self):
        return Cursor(self)

    def execute(self, query, obj=None):
        if not self.sock:
            _lost()
        if not isinstance(query, str):
            raise ProgrammingError("MySQL query must be a string")
        if not self.autocommit and not self._in_transaction:
            self._run_query("START TRANSACTION", None)
            self._in_transaction = True
        self._run_query(query, obj)

    def begin(self):
        if self._in_transaction:
            self.rollback()
        self._run_query("START TRANSACTION", None)
        self._in_transaction = True

    def commit(self):
        if self.sock and self._in_transaction:
            self._run_query("COMMIT", None)
            self._in_transaction = False

    def rollback(self):
        if self.sock and self._in_transaction:
            self._run_query("ROLLBACK", None)
            self._in_transaction = False

    def close(self):
        sock = self.sock
        if sock:
            try:
                self._seq = 0
                self._send_packet(b"\x01")
            finally:
                sock.close()
                self.sock = None
                self._in_transaction = False


def _quote_identifier(identifier):
    if not isinstance(identifier, str) or not identifier:
        raise ProgrammingError("database name must be a non-empty string")
    return "`" + identifier.replace("`", "``") + "`"


def create_database(host, user, password, database, port=3306, use_ssl=True):
    connection = connect(host, user, password, None, port, use_ssl)
    try:
        connection.autocommit = True
        connection.execute("CREATE DATABASE " + _quote_identifier(database))
    finally:
        connection.close()


def drop_database(host, user, password, database, port=3306, use_ssl=True):
    connection = connect(host, user, password, None, port, use_ssl)
    try:
        connection.autocommit = True
        connection.execute("DROP DATABASE " + _quote_identifier(database))
    finally:
        connection.close()
