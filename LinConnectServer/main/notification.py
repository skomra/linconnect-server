#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
import platform
import re

import cherrypy
from gi.repository import Notify
from gi.repository import GLib
import base64

import urllib

from send_email import SendEmail
import datetime
import commands

app_name = 'linconnect-server'
version = "2.20"

# Global Variables
_notification_header = ""
_notification_description = ""

parser = ConfigParser.ConfigParser()

# Must append port because Java Bonjour library can't determine it
_service_name = platform.node()

class Notification(object):

    @staticmethod
    def get_first_n_words(n,s):
        ret = ""
	splitted = s.split()
        for x in range(0,n):
            if x >= len(splitted):
                return ret
	    ret = ret + splitted[x] + " "
        return ret

    @staticmethod
    def filter_tweet(tweet):
        tweet = tweet.lower()
        now = datetime.datetime.now()
        if "nodapl" in tweet:
            print (now.strftime("%Y-%m-%d %H:%M") + " FILTERED: " + tweet)
            return 1
        return 0

    #TODO only removes first instance
    @staticmethod
    def remove_word_by_prefix(prefix, splitted):
            #if not splitted[x].startswith( 'RT' ):
            #else:
                #print ("removing "+ splitted[x])
            #    n += 1
        for x in range(0, len(splitted)):
            if splitted[x] == prefix:
                splitted.remove(splitted[x])
                break
        return splitted

    @staticmethod
    def remove_prefix(prefix, splitted):
        for x in range(0, len(splitted)):
            if splitted[x].startswith("@"):
                splitted[x] = splitted[x][len(prefix):]
        return splitted

    @staticmethod
    def clean_tweet(tweet):
	splitted = tweet.split()
        for x in range(0,len(splitted)):
            if splitted[x].decode('utf-8').endswith(u"\u2026"):
                splitted.remove(splitted[x])
                break
        splitted = Notification.remove_word_by_prefix('RT', splitted)
        splitted = Notification.remove_word_by_prefix("http", splitted)
        splitted = Notification.remove_prefix("@", splitted)
        splitted = Notification.remove_prefix(".@", splitted)
        tweet = " ".join(splitted)
        return tweet

    @staticmethod
    def findUrl(description):
        url = 0;
        splitted = description.split()
        for x in range(0, len(splitted)):
            if splitted[x].startswith("tinyurl.com"):
                url = splitted[x]
        return url

    @staticmethod
    def add_description(header, description):
        output = ""
        if (header == "Rotoworld Baseball"):
            url = Notification.findUrl(description)
            if (url):
                command = ("lynx -dump " + url + " | tail -n +540 2>/dev/null | head -n 25")
                output = commands.getoutput(command)
        output = "\n added \n" + output
        return output

    def notif(self, notificon):
        global _notification_header
        global _notification_description

        # Get notification data from HTTP header
        try:
            new_notification_header = base64.urlsafe_b64decode(cherrypy.request.headers['NOTIFHEADER'])
            new_notification_description = base64.urlsafe_b64decode(cherrypy.request.headers['NOTIFDESCRIPTION'])
        except:
            # Maintain compatibility with old application
            new_notification_header = cherrypy.request.headers['NOTIFHEADER'].replace('\x00', '').decode('iso-8859-1', 'replace').encode('utf-8')
            new_notification_description = cherrypy.request.headers['NOTIFDESCRIPTION'].replace('\x00', '').decode('iso-8859-1', 'replace').encode('utf-8')

        # Ensure the notification is not a duplicate
        if (_notification_header != new_notification_header) \
        or (_notification_description != new_notification_description):
            _notification_header = new_notification_header
            _notification_description = new_notification_description

            new_notification_description = new_notification_description[:-14] #remove (via twitter)

            ts = "https://twitter.com/search?q="

            tweet = self.clean_tweet(new_notification_description)
            twitterSearch = ts + urllib.quote(tweet)
            sixWords = self.get_first_n_words(7,tweet)
            twitterSearchTwo = ts + urllib.quote(sixWords)

            bonus = self.add_description(new_notification_header, new_notification_description)
            now = datetime.datetime.now()
            if (not self.filter_tweet(tweet)):
                SendEmail.send(new_notification_header + " - " +
                               new_notification_description, new_notification_description +
                               "\n\n" + twitterSearch + "\n\n" + twitterSearchTwo +
                               "\n\n" + bonus)
                logmessage = (now.strftime("%Y-%m-%d %H:%M") + " " + new_notification_header +
                              " - " + new_notification_description)
                print (logmessage[:98].replace('\n', ' '))

        return "true"
    notif.exposed = True


