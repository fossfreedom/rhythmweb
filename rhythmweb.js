/*
 Rhythmweb - a web site for your Rhythmbox.
 GTK3 port to work with v2.96 Rhythmbox
 Copyright (c) 2012 fossfreedom and Taylor Raack
 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License along
 with this program; if not, write to the Free Software Foundation, Inc.,
 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
*/

function Rhythmweb() {
	
	var toggleShuffleEl;
	var toggleRepeatEl;
	var playlistBoxEl;
	
	var selectedPlaylist = '';
	var selectedTrack = '';
	
	var reloadWindow = function(data) {
		// some data has changed on the page
		// TODO - reload the page via ajax entirely rather than rebuilding all html
		
		// reload page after 200ms, to ensure that new track has started playing
		setTimeout(function() {document.location.reload();}, 200);
	};
	
	var post = function(params, reload) {
		$.post('/', params, function() { if(reload) { reloadWindow(); }});
	};
	
	var play = function() {
		var params = {'action':'play', 'playlist': selectedPlaylist};
		if(selectedTrack != '') {
			params['track'] = selectedTrack;
		}
		post(params, true);
	};
	
	var previousTrack = function() {
		post({'action':'prev'}, true);
	};
	
	var nextTrack = function() {
		post({'action':'next'}, true);
	};
	
	var volumeUp = function() {
		post({'action':'vol-up'});
	};
	
	var volumeDown = function() {
		post({'action':'vol-down'});
	};
	
	var toggleShuffle = function() {
		post({'action':'toggle-shuffle'});
		
		// change active flag
		toggleShuffleEl.toggleClass('active');
	};
	
	var toggleRepeat = function() {
		post({'action':'toggle-repeat'});
		
		// change active flag
		toggleRepeatEl.toggleClass('active');
	};
	
	var loadPlayQueue = function() {
	    // ajax load of play queue
        $.get('/playqueue',loadPlaylistData);
	};
	
	var loadPlaylist = function(playlistName) {
	    // ajax load of playlist
        $.get('/playlist/' + playlistName,loadPlaylistData);
	};
	
	var loadPlaylistData = function(playlistData) {
	    var tableData = [];
	    
	    var data = playlistData['tracks'];
	    
	    // add each track to the playlist
	    for(var i in data) {
	        var item = data[i];
            tableData.push('<tr id="' + item['id'] + '"><td>' + item['title'] + '</td><td>' + item['artist'] + '</td><td>' + item['album'] + '</td></tr>');	    
	    }
	
	    // show the new playlist
	    $('#playlist tbody').html(tableData.join(''));
	    
	    // set color alternation
	    alternateTrackTableRowColors();
	    
	    selectedPlaylist = playlistData['name'];
	};
	
	var installClickHandlers = function(elementLocator, clickFunction, doubleClickFunction) {
	    // add click handlers to all table elements, current and future
        var agent = navigator.userAgent.toLowerCase();
        if(agent.indexOf('iphone') >= 0 || agent.indexOf('ipad') >= 0 || agent.indexOf('android') >= 0){
            // register double tap handler, but don't use the single tap handler as it's broken
            if(doubleClickFunction != null) {
                $(elementLocator).doubletap(
                    doubleClickFunction,
                    null,
                    300
                );
            }
            
            // install single tap handler
            if(clickFunction != null) {
                $(elementLocator).live('touchend', clickFunction);
            }
        }
        else {
            // non mobile safari - use standard jquery click handlers
            if(clickFunction != null) {
                $(elementLocator).live('click', clickFunction);
            }
            if(doubleClickFunction != null) {
                $(elementLocator).live('dblclick', doubleClickFunction);
            }
        }
	
	};
	
	var addTrackTableClickHandlers = function() {
		installClickHandlers('#playlist tr', handleTrackClicked, handleTrackDoubleClicked);
	};
	
	var handleTrackClicked = function(event) {
		var tr = $(event.currentTarget);
		
		// remove previous selection
		$('#playlist tr').removeClass('selected');
		
		// select the track row
		tr.addClass('selected');
		
		selectedTrack = event.currentTarget.id;
	};
	
	var handlePlaylistClicked = function(event) {
        var div = $(event.currentTarget);
        
        // load the playlist into the window
        if(div.hasClass("playqueue")) {
        	// this is the global play queue
        	loadPlayQueue();
        } else {
        	loadPlaylist(div.html());
        }
        
        // remove previous selection
        $('#playlistbox .playlist_item').removeClass('selected');
        
        // select the track row
        div.addClass('selected');
        
        // clear the selected track
        selectedTrack = '';
    };
	
	var handleTrackDoubleClicked = function(event) {
		post({'action':'play-track','track':event.currentTarget.id,'playlist':$('#playlistbox .selected').html()}, true);
	};
	
	var alternateTrackTableRowColors = function() {
		$('#playlist tr:even').addClass('alt');
	};
	
	var togglePlaylistPaneVisibility = function(){
        $('#main').toggleClass('use-sidebar');
        
        var hasSidebar = $('#main').hasClass('use-sidebar') + '';
        $.cookie("show_playlist_sidebar", hasSidebar);
    };
	
	var createPlaylistListReloader = function() {
	    // create double click handler for playlist
	    installClickHandlers('.playlist_item', handlePlaylistClicked, playPlaylist);
	    
	    // create playlist list reloader
	    // TODO - turn this on once the track list reloads via ajax
	    //setInterval(reloadPlaylists, 30000);
        reloadPlaylists();
	};
	
	var playPlaylist = function(event) {
	    var div = $(event.currentTarget);
        
        var requestedPlaylist = $(event.currentTarget).html();
        
        post({'action':'play-playlist', 'playlist': requestedPlaylist}, true);
	};
	
	var reloadPlaylists = function() {
	   // ajax load of playlists
	   $.get('/playlists',displayPlaylists);
	};
	
	var displayPlaylists = function(playlistData) {
	   // display the new playlists
	   var playlistHTMLs = [];
	   
	   // add play queue
	   var playQueueEl = '<div class="playlist_item playqueue';
	   if(playlistData['selected'] == 'Play Queue') {
		   playQueueEl += ' selected';
	   }
	   playQueueEl += '"	>Play Queue</div>';
	   
	   
	   playlistHTMLs.push(playQueueEl);
	   
	   for(var i in playlistData['playlists']) {
	       var div = '<div class="playlist_item';
	       if(playlistData['selected'] == playlistData['playlists'][i]) {
	           div += ' selected';
	       }
	       div += '">' + playlistData['playlists'][i] + '</div>'
	       playlistHTMLs.push(div);
	   }
	
	   // reload playlist content
	   playlistBoxEl.html(playlistHTMLs.join(""))
	};
	
	var initialize = function() {
		toggleShuffleEl = $('#toggle-shuffle');
		toggleRepeatEl = $('#toggle-repeat');
        playlistBoxEl = $('#playlistbox');
        
        var playlistViewCookie = $.cookie("show_playlist_sidebar");
        if(playlistViewCookie != null && playlistViewCookie == "true") {
            $('#main').addClass('use-sidebar');
        }
		
		$('#play').click(play);
		$('#previous-track').click(previousTrack);
		$('#next-track').click(nextTrack);
		$('#volume-up').click(volumeUp);
		$('#volume-down').click(volumeDown);
        $('#toggle-playlist-view').click(togglePlaylistPaneVisibility);
		toggleShuffleEl.click(toggleShuffle);
		toggleRepeatEl.click(toggleRepeat);
		
		addTrackTableClickHandlers();
		
		alternateTrackTableRowColors();
		
		createPlaylistListReloader();
	};

	initialize();
}


$(document).ready(function() {
	new Rhythmweb();
});
