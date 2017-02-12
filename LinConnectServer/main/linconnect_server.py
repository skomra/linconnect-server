'''
    LinConnect: Mirror Android notifications on Linux Desktop

    Copyright (C) 2013  Will Hauck

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import print_function

# Imports
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
import os
import sys
import signal
import select
import threading
import platform
import re
import glob
import hashlib

import cherrypy
import subprocess
from gi.repository import Notify
from gi.repository import GLib
import pybonjour
import shutil
import base64

import yagmail
import keyring
import urllib

from notification import Notification
from send_email import SendEmail
app_name = 'linconnect-server'
version = "2.20"

# Global Variables
_notification_header = ""
_notification_description = ""

# Configuration
script_dir = os.path.abspath(os.path.dirname(__file__))

def user_specific_location(type, file):
    dir = os.path.expanduser(os.path.join('~/.' + type, app_name))
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return os.path.join(dir, file)

conf_file = user_specific_location('config', 'conf.ini')
icon_path_format = user_specific_location('cache', 'icon_cache_%s.png')

# Clear the icon cache
for icon_cache_file in glob.glob(icon_path_format % '*'):
    os.unlink(icon_cache_file)

old_conf_file = os.path.join(script_dir, 'conf.ini')
if os.path.isfile(old_conf_file):
    if os.path.isfile(conf_file):
        print("Both old and new config files exist: %s and %s, ignoring old one" % (old_conf_file, conf_file))
    else:
        print("Old config file %s found, moving to a new location: %s" % (old_conf_file, conf_file))
        shutil.move(old_conf_file, conf_file)
del old_conf_file

try:
    with open(conf_file):
        print("Loading conf.ini")
except IOError:
    print("Creating conf.ini")
    with open(conf_file, 'w') as text_file:
        text_file.write("""[connection]
port = 9090
enable_bonjour = 1

[other]
enable_instruction_webpage = 1
notify_timeout = 5000""")

parser = ConfigParser.ConfigParser()
parser.read(conf_file)
del conf_file

# Must append port because Java Bonjour library can't determine it
_service_name = platform.node()

def register_callback(sdRef, flags, errorCode, name, regtype, domain):
    if errorCode == pybonjour.kDNSServiceErr_NoError:
        print("Registered Bonjour service " + name)

def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)

def initialize_bonjour():
    sdRef = pybonjour.DNSServiceRegister(name=_service_name,
                                     regtype="_linconnect._tcp",
                                     port=int(parser.get('connection', 'port')),
                                     callBack=register_callback)
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)
    
    try:
        try:
            while True:
                ready = select.select([sdRef], [], [])
                if sdRef in ready[0]:
                    pybonjour.DNSServiceProcessResult(sdRef)
        except KeyboardInterrupt:
            pass
    finally:
        sdRef.close()

def get_local_ip():
    ips = []
    for ip in subprocess.check_output("/sbin/ip address | grep -i 'inet ' | awk {'print $2'} | sed -e 's/\/[^\/]*$//'", shell=True).split("\n"):
        if ip.__len__() > 0 and not ip.startswith("127."):
            ips.append(ip + ":" + parser.get('connection', 'port'))
    return ips

# Initialization
if not Notify.init("com.willhauck.linconnect"):
    raise ImportError("Error initializing libnotify")

# Start Bonjour if desired
if parser.getboolean('connection', 'enable_bonjour') == 1:
    thr = threading.Thread(target=initialize_bonjour)
    thr.start()

config_instructions = "Configuration instructions at http://localhost:" + parser.get('connection', 'port')
print(config_instructions)
notif = Notify.Notification.new("Notification server started (version " + version + ")", config_instructions, "info")
notif.show()

cherrypy.server.socket_host = '0.0.0.0'
cherrypy.server.socket_port = int(parser.get('connection', 'port'))

cherrypy.quickstart(Notification())
