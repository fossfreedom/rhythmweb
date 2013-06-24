#!/bin/bash
SCRIPT_NAME=`basename "$0"`
SCRIPT_PATH=${0%`basename "$0"`}
PLUGIN_PATH="/home/${USER}/.local/share/rhythmbox/plugins/rhythmweb/"  

#build the dirs
mkdir -p $PLUGIN_PATH

sudo cp org.gnome.rhythmbox.plugins.rhythmweb.gschema.xml /usr/share/glib-2.0/schemas/org.gnome.rhythmbox.plugins.rhythmweb.gschema.xml
sudo glib-compile-schemas /usr/share/glib-2.0/schemas/

#copy the files
cp -r "${SCRIPT_PATH}"* "$PLUGIN_PATH"

#remove the install script from the dir (not needed)
rm "${PLUGIN_PATH}${SCRIPT_NAME}"
