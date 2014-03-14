#
# Rhythmweb - a web site for your Rhythmbox.
# GTK3 port to work with v2.96 Rhythmbox
# This is derivate software originally created by Michael Gratton, (c) 2007.
# Copyright (c) 2012 fossfreedom and Taylor Raack
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
try: import simplejson as json
except ImportError: import json
import os
import re
import sys
import time
import socket
from wsgiref.simple_server import WSGIRequestHandler
from wsgiref.simple_server import make_server

from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import RB
from gi.repository import Peas
from rhythmweb_prefs import Preferences

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
    object = GObject.property(type=GObject.GObject)
    port = GObject.property(type=int, default=8000)

    def __init__(self):
        super(RhythmwebPlugin, self).__init__()
 
    def do_activate(self): 
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

        settings = Gio.Settings("org.gnome.rhythmbox.plugins.rhythmweb")
        settings.bind('port', self,
            'port', Gio.SettingsBindFlags.GET)
        
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
            uri = entry.get_ulong(RB.RhythmDBPropType.ENTRY_ID)
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

            self.server.set_playing(artist, album, title, stream, uri)
        else:
            self.server.set_playing(None, None, None, None, None)


class RhythmwebServer(object):

    def __init__(self, hostname, port, plugin):
        self.plugin = plugin
        self.running = True
        self.artist = None
        self.album = None
        self.title = None
        self.stream = None
        self._httpd = make_server(hostname, port, self._wsgi)
        self._watch_cb_id = GObject.io_add_watch(self._httpd.socket,
                                                 GObject.IO_IN,
                                                 self._idle_cb)
        self._cover_db = RB.ExtDB(name='album-art')
        
    def shutdown(self):
        GObject.source_remove(self._watch_cb_id)
        self.running = False
        self.plugin = None

    def set_playing(self, artist, album, title, stream, uri):
        self.artist = artist
        self.album = album
        self.title = title
        self.stream = stream
        self.uri = uri

    #def _open(self, filename):
     #   filename = os.path.join(os.path.dirname(__file__), filename)
      #  return open(filename)

    def _idle_cb(self, source, cb_condition):
        if not self.running:
            return False
        self._httpd.handle_request()
        return True
        
    def _wsgi(self, environ, response):
        path = environ['PATH_INFO']
        
        if path in ('/', ''):
            return self._handle_interface(environ, response)
        elif path == '/playlists':
            return self._handle_playlists(environ, response)
        elif path ==  '/playlist/initial':
            return self._handle_playlist_init(response)
        elif path ==  '/playlist/slice':
            return self._handle_playlist_init(response, environ)
        elif path == '/playlist/current':
            return self._handle_current(response)
        elif re.match("/playlist/.*", path) is not None:
            return self._handle_playlist_info(environ, response, re.match("/playlist/(.*)", path).group(1))
        elif path == '/playqueue':
            return self._handle_playqueue_info(environ, response)
        elif path.startswith('/stock/'):
            return self._handle_stock(environ, response)
        elif path.startswith('/cover/'):
            return self._handle_cover(environ, response)
        else:
            return self._handle_static(environ, response)

    def _handle_interface(self, environ, response):
        player = self.plugin.player
        shell = self.plugin.shell
        db = self.plugin.db
        queue = shell.props.queue_source
        
        playlist_rows = []
        
        if player.get_playing_source() is not None:
            # something is playing; get the track list from the play queue or the current playlists
            playlist_rows = player.get_playing_source().get_entry_view().props.model
        else:
            # nothing is playing,
            # but there are some songs in the play queue; the track listing should show the play queue
            playlist_rows = queue.props.query_model
        
        # handle any action
        if environ['REQUEST_METHOD'] == 'POST':
            try:
                params = parse_post(environ)
                action = params['action'][0]
            except:
                params = []
                action = "unknown"
                
            log('action', action)
            responsetext = ''
            entry = player.get_playing_entry()
            
            if action == 'play' and not entry and \
                not player.get_playing_source():
                    # no current playlist is playing.
                    if 'playlist' in params and len(params['playlist']) > 0:
                        # play the playlist that was requested
                        playlist = params['playlist'][0]
                        log("play", playlist)
                        if(playlist == 'Play Queue'):
                            log("play", "play queue")
                            if playlist_rows.get_size() > 0:
                                log("play", "get size")
                                player.play_entry(iter(playlist_rows).next()[0],
                                                queue)
                                #player.play_entry(playlist_rows[0], queue)
                                responsetext = {'playing':'true'}
                            else:
                                log("play", "no rows in playqueue")
                        else:
                            # get the first track in the requested playlist
                            log("play", "first track")
                            selected_track = None
                            if 'track' in params and len(params['track']) > 0:
                                selected_track = params['track'][0]
                            self._play_track(player, shell, selected_track, playlist)
                            responsetext = {'playing':'true'}
                    else:
                        if playlist_rows.get_size() > 0:
                            log("play", "get size(2)")
                            player.play_entry(iter(playlist_rows).next()[0],
                                            queue)
                            responsetext = {'playing':'true'}
                            #log("play", iter(playlist_rows)[0])
                            #player.play_entry(iter(playlist_rows)[0], queue)
                        else:
                            log("play", "no rows in playqueue(2)")
                        
            elif action == 'play': 
                player.playpause(True)
                r, val = player.get_playing()  
                responsetext = {'playing':val} 
                log("play", "pause") 
            elif action == 'play-track' and 'track' in params and len(params['track']) > 0:
                # user wants to play a specific song in the play list
                track = params['track'][0]
                playlist = ''
                if 'playlist' in params and len(params['playlist']) > 0:
                    playlist = params['playlist'][0]
                self._play_track(player, shell, track, playlist)
            elif action == 'play-playlist' and 'playlist' in params and len(params['playlist']) > 0:
                # user wants to play a specific playlist
                log('play playlist','')
                playlist = params['playlist'][0]
                self._play_playlist(player, shell, playlist)
            elif action == 'pause':
                player.pause() 
                responsetext = {'playing':'false'}
            elif action == 'next':
                player.do_next()
                self.plugin._update_entry(entry)
            elif action == 'prev':
                player.do_previous()
                self.plugin._update_entry(entry)
            elif action == 'stop':
                player.stop()
                responsetext = {'playing':'false'}
            elif action == 'toggle-repeat':
                self._toggle_play_order(player, False)
            elif action == 'toggle-shuffle':
                self._toggle_play_order(player, True)
            elif action == 'vol-up':
                (dummy, vol) = player.get_volume()
                player.set_volume(vol + 0.05)
            elif action == 'vol-down':
                (dummy, vol) = player.get_volume()
                player.set_volume(vol - 0.05)
            else:
                log("dunno1", action)
            
            if entry:
                player.props.db.entry_unref(entry)#Due to RB docs entry should be unrefed when no longer needed
            
            #log("eviron", environ)
            #log("response", response) 
            if responsetext != '':
                response_headers = [('Content-type','application/json; charset=UTF-8')]
                response('200 OK', response_headers)
                return json.dumps(responsetext) 
            else:
                response('204 No Content', [('Content-type','text/plain')])
                return 'OK'

        # generate the playing headline
        title = 'Rhythmweb'
        playing = '<span id="not-playing">Not playing</span>'
        play = ''
        if self.stream or self.title:
            play = 'class="active"'
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

        toggle_repeat_active = ''
        toggle_shuffle_active = ''
        if (player.props.play_order == 'linear-loop') or (player.props.play_order == 'random-by-age-and-rating'):
            toggle_repeat_active = 'class="active"'
        if (player.props.play_order == 'shuffle') or (player.props.play_order == 'random-by-age-and-rating'):
            toggle_shuffle_active = 'class="active"'
    
        r, val = player.get_playing()
        # display the page
        player_html = open(resolve_path('player.html'))
        
        result = player_html.read() % { 'title': title,
                                      'play': play,
                                      'playing': playing,
                                      'toggle_repeat_active': toggle_repeat_active,
                                      'toggle_shuffle_active': toggle_shuffle_active,
                                      'currentlyplaying': val 
                                    }
        response_headers = [('Content-type','text/html; charset=UTF-8'),
                            ('Content-Length', str(len(result)))]
        response('200 OK', response_headers)
        
        player_html.close()
        return result
                                      
    def _handle_playlists(self, environ, response):
        # get a list of all of the playlists
        playlists = []
        
        current_playlist_name = ''
        
        if self.plugin.player.get_playing_source() is not None:
            current_playlist_name = self.plugin.player.get_playing_source().props.name
            if current_playlist_name.startswith('Play Queue'):
                # strip the number of play queue tracks from the playlist name
                current_playlist_name = "Play Queue"
        else:
            # if no playlist is playing, the current playlist should be the play queue
            current_playlist_name = "Play Queue"
        
        playlist_model_entries = self.plugin.shell.props.playlist_manager.get_playlists()
        if playlist_model_entries:
            for playlist in playlist_model_entries:
                if playlist.props.is_local and \
                    isinstance(playlist, RB.StaticPlaylistSource):
                    playlists.append(playlist.props.name)
    
        # return playlists as json
        playlist_data = {'selected': current_playlist_name, 'playlists': playlists};
        response_headers = [('Content-type','application/json; charset=UTF-8')]
        response('200 OK', response_headers)
        return json.dumps(playlist_data)
        
    
    def _handle_playlist_info(self, environ, response, playlist_name):
    
        log('getting playlist info for playlist ', playlist_name)
    
        playlist_candidate = self._find_playlist_by_name(playlist_name)
        if playlist_candidate is not None:
            playlist_rows = playlist_candidate.get_query_model()
            
            return self._process_tracks_to_json_response(playlist_name, playlist_rows, response)
            
        # if we get here, the playlist wasn't found
        response('404 Not Found', [])
        return json.dumps({"error": "playlist not found"})
        
    def _handle_playlist_init(self, response, environ = None):
        player = self.plugin.player

        if player.get_playing_source() is not None:
            playlist_rows = player.get_playing_source().get_entry_view().props.model
        else:
            playlist_rows = player.props.source.get_entry_view().props.model
            
        if environ is not None:
            params = parse_post(environ)
            start = int(params['start'][0])
            end = int(params['end'][0])
            playlist_rows = list(playlist_rows)[start:end]
            
        return self._process_tracks_to_json_response('initial', playlist_rows, response)

    def _handle_current(self, response):
        title = ''
        artist = ''
        album = ''
        if self.title:
            title = self.title
        if self.artist:
            artist = self.artist
        if self.album:
            album =  self.album
            
        cover = self._get_cover_name_for_playing_track()
        
        return_data = {'title': title, 'artist': artist, 'album': album, 'stream': self.stream, 'cover': cover};
        response_headers = [('Content-type','application/json; charset=UTF-8')]
        response('200 OK', response_headers)
        return json.dumps(return_data)
    
    def _handle_playqueue_info(self, environ, response):
    
        log('getting playqueue info', '')
        
        shell = self.plugin.shell
        queue = shell.props.queue_source
        playlist_rows = queue.props.query_model
        
        return self._process_tracks_to_json_response("Play Queue", playlist_rows, response)
        
    def _process_tracks_to_json_response(self, playlist_name, playlist_rows, response):
        tracks = []

        for row in playlist_rows:
            track_info = row[0]
            track = {'id': track_info.get_ulong(RB.RhythmDBPropType.ENTRY_ID),
                    'title': track_info.get_string(RB.RhythmDBPropType.TITLE),
                    'artist': track_info.get_string(RB.RhythmDBPropType.ARTIST),
                    'album': track_info.get_string(RB.RhythmDBPropType.ALBUM)}
            
            tracks.append(track)

        playlist_data = {'name': playlist_name, 'tracks': tracks};
        response_headers = [('Content-type','application/json; charset=UTF-8')]
        response('200 OK', response_headers)

        return json.dumps(playlist_data)
                              
    def _play_track(self, player, shell, track, playlist):
        source = ''
        
        log("playing from playlist ", playlist)
        if playlist == '':
            # find the current playing source, or select the active queue source
            if player.get_playing_source() is not None:
               source = player.get_playing_source()
            else:
                source = shell.props.queue_source
        else:
            # play in a specific playlist
            source = self._find_playlist_by_name(playlist)
        
        if track is not None:
            # find the rhythmbox database entry for the track uri
            entry = shell.props.db.entry_lookup_by_id(long(track))
        else:
            log('no specific track requested; playing from top','')
            playlist_rows = source.get_query_model()
            if playlist_rows.get_size() > 0:
                log('got entries for playlist','')
                entry = iter(playlist_rows).next()[0]
                
        
        if entry is not None:
            log('about to play entry ', entry)
            # play the track on the source
            player.play_entry(entry, source)
        
    def _find_playlist_by_name(self, playlist_name):
        playlist_model_entries = self.plugin.shell.props.playlist_manager.get_playlists()
        if playlist_model_entries:
            for playlist_candidate in playlist_model_entries:
                if playlist_candidate.props.name == playlist_name:
                    # found the right playlist
                    return playlist_candidate

        #assume the queue if playlist is not found
        return self.plugin.shell.props.queue_source
        
    def _play_playlist(self, player, shell, playlist_name):
        playlist_candidate = self._find_playlist_by_name(playlist_name)
        if playlist_candidate is not None:
            playlist_rows = playlist_candidate.get_query_model()
            
            for row in playlist_rows:
                # find the first track in this playlist
                entry = shell.props.db.entry_lookup_by_id(row[0].get_ulong(RB.RhythmDBPropType.ENTRY_ID))
                # play the first track
                player.play_entry(entry, playlist_candidate)
                break

    def _toggle_play_order(self, player, toggle_shuffle):
        # get current play order
        current_play_order = player.props.play_order
        
        # determine which next shuffle shall be
        if current_play_order == 'linear':
            current_play_order = 'shuffle' if toggle_shuffle == True else 'linear-loop'
        elif current_play_order == 'shuffle':
            current_play_order = 'linear' if toggle_shuffle == True else 'random-by-age-and-rating'
        elif current_play_order == 'linear-loop':
            current_play_order = 'random-by-age-and-rating' if toggle_shuffle == True else 'linear'
        else:
            current_play_order = 'linear-loop' if toggle_shuffle == True else 'shuffle'
        
        # set play order state
        Gio.Settings.new('org.gnome.rhythmbox.player').set_string("play-order",current_play_order)

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
            fname = iconinfo.get_filename()
            boolval = False
            # use gio to guess at the content type based on filename
            
            content_type, val = Gio.content_type_guess(filename=fname, data=None)

            icon = open(fname)
            lastmod = time.gmtime(os.path.getmtime(fname))
            lastmod = time.strftime("%a, %d %b %Y %H:%M:%S +0000", lastmod)
            response_headers = [('Content-type',content_type),
                                ('Last-Modified', lastmod)]
            response('200 OK', response_headers)
            result = icon.read()
            icon.close()
        
            return result
        else:
            log("icon", "none")
            response_headers = [('Content-type','text/plain')]
            response('404 Not Found', response_headers)
            return 'Stock not found: %s' % stock_id

    def _handle_cover(self, environ, response):
        fname = self._get_cover_name_for_playing_track()
            
        # use gio to guess at the content type based on filename
        content_type, val = Gio.content_type_guess(filename=fname, data=None)

        icon = open(fname)
        lastmod = time.gmtime(os.path.getmtime(fname))
        lastmod = time.strftime("%a, %d %b %Y %H:%M:%S +0000", lastmod)
        response_headers = [('Content-type',content_type),
                            ('Last-Modified', lastmod)]
        response('200 OK', response_headers)
        
        result = icon.read()
        icon.close()
        
        return result
        
    def _get_cover_name_for_playing_track(self):
        player = self.plugin.player

        fname = None
        if player.get_playing_source() is not None:
            # something is playing; 
            entry = player.get_playing_entry()
            key = entry.create_ext_db_key(RB.RhythmDBPropType.ALBUM)
            
            player.props.db.entry_unref(entry)
            
            fname = self._cover_db.lookup(key)
            log("handle", fname)

        if not fname:
            # nothing is playing or no cover
            fname = 'rhythmbox-missing-artwork.svg'
            
        return fname

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