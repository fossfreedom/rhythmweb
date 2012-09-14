#
# Rhythmweb - a web site for your Rhythmbox.
# GTK3 port to work with v2.96 Rhythmbox
# This is derivate software originally created by Michael Gratton, (c) 2007.
# Copyright (c) 2012
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import cStringIO
import cgi
import os
import sys
import time
import socket
from wsgiref.simple_server import WSGIRequestHandler
from wsgiref.simple_server import make_server

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import RB
from gi.repository import Peas

import rb

# try to load avahi, don't complain if it fails
try:
    import dbus
    import avahi
    use_mdns = True
except:
    use_mdns = False


class RhythmwebPlugin(GObject.GObject, Peas.Activatable):
    __gtype_name__ = 'RhythmwebPlugin'
    object = GObject.Property(type=GObject.GObject)

    def __init__(self):
        super(RhythmwebPlugin, self).__init__()

    def do_activate (self):
        self.shell = self.object
        self.player = self.shell.props.shell_player
        self.db = self.shell.props.db
        self.shell_cb_ids = (
            self.player.connect ('playing-song-changed',
                                 self._playing_entry_changed_cb),
            self.player.connect ('playing-changed',
                                 self._playing_changed_cb)
            )
        self.db_cb_ids = (
            self.db.connect ('entry-extra-metadata-notify',
                             self._extra_metadata_changed_cb)
            ,)
        self.port = 8000
        self.server = RhythmwebServer('', self.port, self)
        self._mdns_publish()

    def do_deactivate(self):
        self._mdns_withdraw()
        self.server.shutdown()
        self.server = None

        for id in self.shell_cb_ids:
            self.player.disconnect(id)

        for id in self.db_cb_ids:
            self.db.disconnect(id)

        self.player = None
        self.shell = None
        self.db = None

    def _mdns_publish(self):
        if use_mdns:
            bus = dbus.SystemBus()
            avahi_bus = bus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER)
            avahi_svr = dbus.Interface(avahi_bus, avahi.DBUS_INTERFACE_SERVER)

            servicetype = '_http._tcp'
            servicename = 'Rhythmweb on %s' % (socket.gethostname())

            eg_path = avahi_svr.EntryGroupNew()
            eg_obj = bus.get_object(avahi.DBUS_NAME, eg_path)
            self.entrygroup = dbus.Interface(eg_obj,
                                             avahi.DBUS_INTERFACE_ENTRY_GROUP)
            self.entrygroup.AddService(avahi.IF_UNSPEC,
                                       avahi.PROTO_UNSPEC,
                                       0,
                                       servicename,
                                       servicetype,
                                       "",
                                       "",
                                       dbus.UInt16(self.port),
                                       ())
            self.entrygroup.Commit()

    def _mdns_withdraw(self):
        if use_mdns and self.entrygroup != None:
            self.entrygroup.Reset()
            self.entrygroup.Free()
            self.entrygroup = None

    def _playing_changed_cb(self, player, playing):
        self._update_entry(player.get_playing_entry())

    def _playing_entry_changed_cb(self, player, entry):
        self._update_entry(entry)

    def _extra_metadata_changed_cb(self, db, entry, field, metadata):
        if entry == self.player.get_playing_entry():
            self._update_entry(entry)

    def _update_entry(self, entry):
        if entry:
            artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
            album = entry.get_string(RB.RhythmDBPropType.ALBUM)
            title = entry.get_string(RB.RhythmDBPropType.TITLE)
            stream = None
            stream_title = \
                self.db.entry_request_extra_metadata(entry,
                                                     'rb:stream-song-title')

            if stream_title:
                stream = title
                title = stream_title
                if not artist:
                    artist = self.db.\
                        entry_request_extra_metadata(entry,
                                                     'rb:stream-song-artist')

                if not album:
                    album = self.db.\
                            entry_request_extra_metadata(entry,
                                                         'rb:stream-song-album')

            self.server.set_playing(artist, album, title, stream)
        else:
            self.server.set_playing(None, None, None, None)


class RhythmwebServer(object):

    def __init__(self, hostname, port, plugin):
        self.plugin = plugin
        self.running = True
        self.artist = None
        self.album = None
        self.title = None
        self.stream = None
        self._httpd = make_server(hostname, port, self._wsgi,
                                  handler_class=LoggingWSGIRequestHandler)
        self._watch_cb_id = GObject.io_add_watch(self._httpd.socket,
                                                 GObject.IO_IN,
                                                 self._idle_cb)
	
    def shutdown(self):
        GObject.source_remove(self._watch_cb_id)
        self.running = False
        self.plugin = None

    def set_playing(self, artist, album, title, stream):
        self.artist = artist
        self.album = album
        self.title = title
        self.stream = stream

    def _open(self, filename):
        filename = os.path.join(os.path.dirname(__file__), filename)
        return open(filename)

    def _idle_cb(self, source, cb_condition):
        if not self.running:
            return False
        self._httpd.handle_request()
        return True

    def _wsgi(self, environ, response):
        path = environ['PATH_INFO']
        if path in ('/', ''):
            return self._handle_interface(environ, response)
        elif path.startswith('/stock/'):
            return self._handle_stock(environ, response)
        else:
            return self._handle_static(environ, response)

    def _handle_interface(self, environ, response):
        player = self.plugin.player
        shell = self.plugin.shell
        db = self.plugin.db
        queue = shell.props.queue_source
        playlist_rows = queue.props.query_model

        
        # handle any action
        if environ['REQUEST_METHOD'] == 'POST':
            try:
                params = parse_post(environ)
                if 'action' in params:
                    action = params['action'][0]
                    if action == 'play':
                        if not player.get_playing_entry():
                            #log("play", "not playing")
                            if not player.get_playing_source():
                                #log("play", "not source")
                                if playlist_rows.get_size() > 0:
                                    #log("play", "get size")
                                    player.play_entry(iter(playlist_rows).next()[0],
                                                    queue)
                                    #player.play_entry(playlist_rows[0], queue)
                            else:
                                #log("play", "play")
                                player.play()
                        else:
                            player.playpause(True)
                            #log("play", "pause")
                    elif action == 'pause':
                        player.pause()
                    elif action == 'next':
                        player.do_next()
                    elif action == 'prev':
                        player.do_previous()
                    elif action == 'stop':
                        player.stop()
                    elif action == 'vol-up':
                        (vol, another) = player.get_volume()
                        player.set_volume(vol+0.1)
                    elif action == 'vol-down':
                        (vol, another) = player.get_volume()
                        player.set_volume(vol - 0.1)
                    else:
                        log("dunno1", action)
                else:
                    log("dunno2","no action")
            except:
                pass
                    
            #log("eviron", environ)
            #log("response", response)
            response('204 No Content', [('Content-type','text/plain')])
            return 'OK'

        # generate the playing headline
        title = 'Rhythmweb'
        playing = '<span id="not-playing">Not playing</span>'
        if self.stream or self.title:
            playing = ''
            title = ''
            if self.title:
                playing = '<cite id="title">%s</cite>' % self.title
                title = self.title
            if self.artist:
                playing = ('%s by <cite id="artist">%s</cite>' %
                           (playing, self.artist))
                title = '%s by %s' % (title, self.artist)
            if self.album:
                playing = ('%s from <cite id="album">%s</cite>' %
                           (playing, self.album))
                title = '%s from %s' % (title, self.album)
            if self.stream:
                if playing:
                    playing = ('%s <cite id="stream">(%s)</cite>' %
                               (playing, self.stream))
                    title = '%s (%s)' % (title, self.album)
                else:
                    playing = self.stream
                    title = self.stream

        # generate the playlist
        playlist = '<tr><td colspan="3">Playlist is empty</td></tr>'
        if playlist_rows.get_size() > 0:
            outputstr = cStringIO.StringIO()
            for row in playlist_rows:
                entry = row[0]
                outputstr.write('<tr><td>')
                outputstr.write(entry.get_string(RB.RhythmDBPropType.TITLE))
                outputstr.write('</td><td>')
                outputstr.write(entry.get_string(RB.RhythmDBPropType.ARTIST))
                outputstr.write('</td><td>')
                outputstr.write(entry.get_string(RB.RhythmDBPropType.ALBUM))
                outputstr.write('</td></tr>')
            playlist = outputstr.getvalue()
            outputstr.close()

        # handle player state
        play = ''
        refresh = ''
        if player.get_playing():
            play = 'class="active"'
            duration = player.get_playing_song_duration()
            if duration > 0:
                try:
                    (refresh,another) = player.get_playing_time()
                    refresh = duration - refresh + 2 
                except:
                    refresh = duration + 2
                    
                refresh = '<meta http-equiv="refresh" content="%s">' % refresh

        #log('title', title)
        #log('refresh', refresh)
        #log('play', play)
        #log('playing', playing)
        #log('playlist', playlist)
	
        # display the page
        player_html = open(resolve_path('player.html'))
        response_headers = [('Content-type','text/html; charset=UTF-8')]
        response('200 OK', response_headers)
        return player_html.read() % { 'title': title,
                                      'refresh': refresh,
                                      'play': play,
                                      'playing': playing,
                                      'playlist': playlist }

    def _handle_stock(self, environ, response):
        path = environ['PATH_INFO']
        stock_id = path[len('/stock/'):]

        icons = Gtk.IconTheme.get_default()
	
        iconinfo = icons.lookup_icon(stock_id, 24, 0)
        if not iconinfo:
            iconinfo = icons.lookup_icon(stock_id, 32, 0)
        if not iconinfo:
            iconinfo = icons.lookup_icon(stock_id, 48, 0)
        if not iconinfo:
            iconinfo = icons.lookup_icon(stock_id, 16, 0)

        if iconinfo:
            filename = iconinfo.get_filename()
            icon = open(filename)
            lastmod = time.gmtime(os.path.getmtime(filename))
            lastmod = time.strftime("%a, %d %b %Y %H:%M:%S +0000", lastmod)
            response_headers = [('Content-type','image/png'),
                                ('Last-Modified', lastmod)]
            response('200 OK', response_headers)
            return icon
        else:
            response_headers = [('Content-type','text/plain')]
            response('404 Not Found', response_headers)
            return 'Stock not found: %s' % stock_id

    def _handle_static(self, environ, response):
        rpath = environ['PATH_INFO']

        path = rpath.replace('/', os.sep)
        path = os.path.normpath(path)
        if path[0] == os.sep:
            path = path[1:]

        path = resolve_path(path)

        if os.path.isfile(path):
            lastmod = time.gmtime(os.path.getmtime(path))
            lastmod = time.strftime("%a, %d %b %Y %H:%M:%S +0000", lastmod)
            response_headers = [('Content-type','text/css'),
                                ('Last-Modified', lastmod)]
            response('200 OK', response_headers)
            return open(path)
        else:
            response_headers = [('Content-type','text/plain')]
            response('404 Not Found', response_headers)
            return 'File not found: %s' % rpath


class LoggingWSGIRequestHandler(WSGIRequestHandler):

    def log_message(self, format, *args):
        # RB redirects stdout to its logging system, to these
        # request log messages, run RB with -D rhythmweb
        sys.stdout.write("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))


def parse_post(environ):
    if 'CONTENT_TYPE' in environ:
        length = -1
        if 'CONTENT_LENGTH' in environ:
            length = int(environ['CONTENT_LENGTH'])
        if environ['CONTENT_TYPE'].startswith('application/x-www-form-urlencoded'):
            return cgi.parse_qs(environ['wsgi.input'].read(length))
        if environ['CONTENT_TYPE'].startswith('multipart/form-data'):
            return cgi.parse_multipart(environ['wsgi.input'].read(length))
    return None

def return_redirect(path, environ, response):
    if not path.startswith('/'):
        path_prefix = environ['REQUEST_URI']
        if path_prefix.endswith('/'):
            path = path_prefix + path
        else:
            path = path_prefix.rsplit('/', 1)[0] + path
    scheme = environ['wsgi.url_scheme']
    if 'HTTP_HOST' in environ:
        authority = environ['HTTP_HOST']
    else:
        authority = environ['SERVER_NAME']
    port = environ['SERVER_PORT']
    if ((scheme == 'http' and port != '80') or
        (scheme == 'https' and port != '443')):
        authority = '%s:%s' % (authority, port)
    location = '%s://%s%s' % (scheme, authority, path)
    status = '303 See Other'
    response_headers = [('Content-Type', 'text/plain'),
                        ('Location', location)]
    response(status, response_headers)

    #log("response", response)
    return [ 'Redirecting...' ]

def resolve_path(path):
    return os.path.join(os.path.dirname(__file__), path)

def log(message, args):
    sys.stdout.write("log %s:[%s]\n" % (message, args))

