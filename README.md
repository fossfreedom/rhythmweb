rhythmweb
=========

GTK3 port of the original rhythmweb v0.1x GTK2 plugin - for Rhythmbox v2.96 and above


Original implementation by Michael Gratton 
Enhancements by Szymon Pacanowski, fossfreedom & Taylor Raack

 - fossfreedom <foss.freedom@gmail.com>, website - https://github.com/fossfreedom

[![Flattr Button](http://api.flattr.com/button/button-compact-static-100x17.png "Flattr This!")](https://flattr.com/thing/1237286/fossfreedomrhythmweb-on-GitHub "fossfreedom")  [![paypaldonate](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=KBV682WJ3BDGL)

How to use:

1. Extract the folder and its contents to ~/.local/share/rhythmbox/plugins

If using debian & ubuntu derivatives `sudo apt-get install git`

Rhythmbox 2.96 - 2.99.1

<pre>

git clone https://github.com/fossfreedom/rhythmweb.git
cd rhythmweb
./install.sh

</pre>

Rhythmbox 3.0.1 and later

<pre>

git clone https://github.com/fossfreedom/rhythmweb.git
cd rhythmweb
./install.sh --rb3


2. Enable the rhythmweb plugin

3. Launch your browser and browse to localhost:8000

N.B. you can change the port number (8000) in the plugin preferences

![Imgur](http://i.imgur.com/2GiNZ.png)

Tested Platforms
----------------
 - Android 4.2.2 / Google Chrome 27.0.1453.90
 - Ipod/IPad / Safari
 - Mac OS X 10.7.4 / Safari 6.0
 - Mac OS X 10.7.4 / Firefox 14.0.1
 - Mac OS X 10.7.4 / Chrome 21.0
 - Win XP SP3 / Firefox 6.0
 - Win XP SP3 / IE 8.0
 - Win XP SP3 / Chrome 21.0: Pass

Thanks
======

1. thank-you to dinoboy197 for various fix-ups and adding toggle-buttons 
2. thanks to https://github.com/alex116 for adding Android support
3. thanks to Szymon Pacanowski for the major speed and other enhancements update
