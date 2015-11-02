"""General utility functions.
"""

import re
import socket
import threading

from stomp.backward import decode, NULL


## List of all host names (unqualified, fully-qualified, and IP
# addresses) that refer to the local host (both loopback interface
# and external interfaces).  This is used for determining
# preferred targets.
LOCALHOST_NAMES = ["localhost", "127.0.0.1"]

try:
    LOCALHOST_NAMES.append(socket.gethostbyname(socket.gethostname()))
except:
    pass

try:
    LOCALHOST_NAMES.append(socket.gethostname())
except:
    pass

try:
    LOCALHOST_NAMES.append(socket.getfqdn(socket.gethostname()))
except:
    pass

##
# Used to parse STOMP header lines in the format "key:value",
#
HEADER_LINE_RE = re.compile('(?P<key>[^:]+)[:](?P<value>.*)')

##
# As of STOMP 1.2, lines can end with either line feed, or carriage return plus line feed.
#
PREAMBLE_END_RE = re.compile(b'\n\n|\r\n\r\n')

##
# As of STOMP 1.2, lines can end with either line feed, or carriage return plus line feed.
#
LINE_END_RE = re.compile('\n|\r\n')


def default_create_thread(callback):
    """
    Default thread creation - used to create threads when the client doesn't want to provide their
    own thread creation.

    :param callback: the callback function provided to threading.Thread
    """
    thread = threading.Thread(None, callback)
    thread.daemon = True  # Don't let thread prevent termination
    thread.start()
    return thread


def is_localhost(host_and_port):
    """
    Return 1 if the specified host+port is a member of the 'localhost' list of hosts, 2 if not (predominately used
    as a sort key.

    :param host_and_port: tuple containing host (string) and port (number)
    """
    (host, _) = host_and_port
    if host in LOCALHOST_NAMES:
        return 1
    else:
        return 2


def parse_headers(lines, offset=0):
    """
    Parse the headers in a STOMP response

    :param lines: the lines received in the message response
    :param offset: the starting line number
    """
    headers = {}
    for header_line in lines[offset:]:
        header_match = HEADER_LINE_RE.match(header_line)
        if header_match:
            key = header_match.group('key')
            key = key.replace('\\n', '\n').replace('\\r', '\r').replace('\\\\', '\\').replace('\\c', ':')
            if key not in headers:
                value = header_match.group('value')
                value = value.replace('\\n', '\n').replace('\\r', '\r').replace('\\\\', '\\').replace('\\c', ':')
                headers[key] = value
    return headers


def parse_frame(frame):
    """
    Parse a STOMP frame into a (frame_type, headers, body) tuple,
    where frame_type is the frame type as a string (e.g. MESSAGE),
    headers is a map containing all header key/value pairs, and
    body is a string containing the frame's payload.

    :param frame: the frame received from the server (as a string)
    """
    f = Frame()
    if frame == b'\x0a':
        f.cmd = 'heartbeat'
        return f

    mat = PREAMBLE_END_RE.search(frame)
    preamble_end = -1
    if mat:
        preamble_end = mat.start()
    if preamble_end == -1:
        preamble_end = len(frame)
    preamble = decode(frame[0:preamble_end])
    preamble_lines = LINE_END_RE.split(preamble)
    f.body = frame[preamble_end + 2:]

    # Skip any leading newlines
    first_line = 0
    while first_line < len(preamble_lines) and len(preamble_lines[first_line]) == 0:
        first_line += 1

    # Extract frame type/command
    f.cmd = preamble_lines[first_line]

    # Put headers into a key/value map
    f.headers = parse_headers(preamble_lines, first_line + 1)

    return f


def merge_headers(header_map_list):
    """
    Helper function for combining multiple header maps into one.

    :param header_map_list: list of maps
    """
    headers = {}
    for header_map in header_map_list:
        headers.update(header_map)
    return headers


def calculate_heartbeats(shb, chb):
    """
    Given a heartbeat string from the server, and a heartbeat tuple from the client,
    calculate what the actual heartbeat settings should be.

    :param shb: server heartbeat numbers
    :param chb: client heartbeat numbers
    """
    (sx, sy) = shb
    (cx, cy) = chb
    x = 0
    y = 0
    if cx != 0 and sy != '0':
        x = max(cx, int(sy))
    if cy != 0 and sx != '0':
        y = max(cy, int(sx))
    return x, y


def convert_frame_to_lines(frame):
    """
    Convert a frame to a list of lines separated by newlines.

    :param frame: the Frame object to convert
    """
    lines = []
    if frame.cmd:
        lines.append(frame.cmd)
        lines.append("\n")
    for key, vals in sorted(frame.headers.items()):
        if vals is None:
            continue
        if type(vals) != tuple:
            vals = (vals,)
        for val in vals:
            lines.append("%s:%s\n" % (key, val))
    lines.append("\n")
    if frame.body:
        lines.append(frame.body)

    if frame.cmd:
        lines.append(NULL)
    return lines


def length(s):
    """
    Null (none) safe length function.

    :param s: the string to return length of (None allowed)
    """
    if s is not None:
        return len(s)
    return 0


class Frame:
    """
    A STOMP frame (or message).
    
    :param cmd: the protocol command
    :param headers: a map of headers for the frame
    :param body: the content of the frame.
    """
    def __init__(self, cmd=None, headers={}, body=None):
        self.cmd = cmd
        self.headers = headers
        self.body = body

    def __str__(self):
        return '{cmd=%s,headers=[%s],body=%s}' % (self.cmd, self.headers, self.body)
