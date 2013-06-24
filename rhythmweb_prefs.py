# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2013 - fossfreedom
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import PeasGtk
from gi.repository import RB

import rb

class Preferences(GObject.Object, PeasGtk.Configurable):
    '''
    Preferences for the Rhythmweb Plugin. It holds the settings for
    the plugin and also is the responsible of creating the preferences dialog.
    '''
    __gtype_name__ = 'RhythmwebPreferences'
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        '''
        Initialises the preferences
        ''' 
        self.settings = Gio.Settings("org.gnome.rhythmbox.plugins.rhythmweb")
        GObject.Object.__init__(self)

    def btn_apply_clicked(self, widget, instance ):
        '''
        Sets the preferences value to the value entered in the text field in the preferences
        '''
        try:
            instance.settings['port'] = int(instance.builder.get_object('textfieldport').get_text())
            instance.builder.get_object('restartplz').set_visible(True)
        except:
            print 'rhythmweb: failed to set port to value from text field'

    def do_create_configure_widget(self):
        '''
        Creates the plugin's preferences dialog
        '''
        # create the ui
        self.builder = Gtk.Builder()
        self.builder.add_from_file(rb.find_plugin_file(self, 'ui/rhythmweb_prefs.ui'))
        #builder.connect_signals(self)
        
        textinput = self.builder.get_object('textfieldport')
        textinput.set_text(str(self.settings['port']))
        self.builder.get_object('restartplz').set_visible(False)
        self.builder.get_object('buttonapply').connect('clicked', self.btn_apply_clicked, self )
        # return the dialog
        return self.builder.get_object('main_notebook')

    def get_port(self):
        '''
        Returns the current port
        '''
        return self.settings['port']

