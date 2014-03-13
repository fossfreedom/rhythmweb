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
var services = new function() {
	var baseUrl = '/playlist/',
		getInitial = function() {
			return $.getJSON(baseUrl + 'initial');
		},
		getCurrent = function() {
			return $.getJSON(baseUrl + 'current');
		},
		getSlice = function(data) {
			return $.post(baseUrl + 'slice', data);
		};
		
	return {
		getInitial: getInitial,
		getCurrent: getCurrent,
		getSlice: getSlice
	};
}();

function Rhythmweb() {
	
	var toggleShuffleEl = $('#toggle-shuffle'),
		toggleRepeatEl = $('#toggle-repeat'),
		playlistBoxEl = $('#playlistbox'),
		selectedPlaylist = '',
		selectedTrack = '',
		sliceStep = 524;
	
	function post(params, reload, callback) {
		$.post('/', 
			params, 
			function(data, textstatus, xhr) { 	  
				if (reload) {
					loadCurrentPlayingSong();
				}
				if (callback) {
					callback(params, reload, xhr);
				}
			});
	}

	function setPlaybutton(playing){
		var playbutton = $('#play'),
			img = $('#play img');
			
		playbutton.attr('isplaying', playing);

		if (playing) {
			img.attr('src', 'stock/gtk-media-pause');
			playbutton.html('Pause').prepend(img);
			playbutton.addClass('active');
		}
		else {
			img.attr('src', 'stock/gtk-media-play-ltr');
			playbutton.html('Play').prepend(img);
			playbutton.removeClass('active');
		}
	}
	
	function play() {
		var params = {
			'action': $("#play").attr("isplaying").toLowerCase() === "true" ? "pause" : "play",
			'playlist': selectedPlaylist
		};
 
		if (selectedTrack !== '') {
			params.track = selectedTrack;
		}
		post(params, false,
			function(ig, nore, xhr){
				var obj = JSON.parse(xhr.responseText || "");	
				setPlaybutton(String(obj.playing).toLowerCase() === "true");
			}
		);
	}
	
	function previousTrack() {
		post({'action': 'prev'}, false);
		loadCurrentPlayingSong();
	}
	
	function nextTrack() {
		post({'action': 'next'}, false);
		loadCurrentPlayingSong();
	}
	
	function volumeUp() {
		post({'action': 'vol-up'});
	}
	
	function volumeDown() {
		post({'action':'vol-down'});
	}
	
	function toggleShuffle() {
		post({'action':'toggle-shuffle'});
		
		// change active flag
		toggleShuffleEl.toggleClass('active');
	}
	
	function toggleRepeat() {
		post({'action':'toggle-repeat'});
		
		// change active flag
		toggleRepeatEl.toggleClass('active');
	}
	
	function loadPlayQueue() {
	    // ajax load of play queue
        $.get('/playqueue',loadPlaylistData);
	}
	
	function loadPlaylist(playlistName) {
	    // ajax load of playlist
        $.get('/playlist/' + playlistName,loadPlaylistData);
	}
	
	function loadPlaylistData(playlistData) {
	    var tableData = '',
			data = playlistData.tracks;
	    
	    // add each track to the playlist
	    for(var i in data) {
	        var item = data[i];
			tableData += '<tr id="' + item.id + '"><td>' + item.title + '</td><td>' + item.artist + '</td><td>' + item.album + '</td></tr>';
		}
	
	    // show the new playlist
		$('#playlist').append('<tbody>' + tableData + '</tbody>');
	    
	    // set color alternation
	    alternateTrackTableRowColors();
	    
	    selectedPlaylist = playlistData.name;
	}
	
	function installClickHandlers(elementLocator, clickFunction, doubleClickFunction) {
	    // add click handlers to all table elements, current and future
        var agent = navigator.userAgent.toLowerCase();
        if (agent.indexOf('iphone') >= 0 || agent.indexOf('ipad') >= 0 || agent.indexOf('android') >= 0){
            // register double tap handler, but don't use the single tap handler as it's broken
            if(doubleClickFunction !== null) {
                $(elementLocator).doubletap(
                    doubleClickFunction,
                    null,
                    300
                );
            }
            
            // install single tap handler
            if (clickFunction !== null) {
                $(elementLocator).live('touchend', clickFunction);
            }
        } else {
            // non mobile safari - use standard jquery click handlers
            if(clickFunction !== null) {
                $(elementLocator).live('click', clickFunction);
            }
            if(doubleClickFunction !== null) {
                $(elementLocator).live('dblclick', doubleClickFunction);
            }
        }
	}
	
	function addTrackTableClickHandlers() {
		installClickHandlers('#playlist tr', handleTrackClicked, handleTrackDoubleClicked);
	}
	
	function handleTrackClicked(event) {
		var tr = $(event.currentTarget);
		
		// remove previous selection
		$('#playlist tr').removeClass('selected');
		
		// select the track row
		tr.addClass('selected');
		
		selectedTrack = event.currentTarget.id;
	}
	
	function handlePlaylistClicked(event) {
        var div = $(event.currentTarget);
        
        // load the playlist into the window
        if (div.hasClass("playqueue")) {
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
    }
	
	function handleTrackDoubleClicked(event) {
		var targ = event.currentTarget,
			trData = $("td", $(targ)),
			title = $(trData[0]).text();

		post({'action':'play-track','track':targ.id,'playlist':$('#playlistbox .selected').html()}, false);
		
		$('#playing').html('<cite id="title">' + title + '</cite> by <cite id="artist">' + $(trData[1]).text() +
			'</cite> from <cite id="album">' + $(trData[2]).text() + '</cite>' );
		$(document).attr('title', title);
		handleTrackClicked(event);
	}
	
	function alternateTrackTableRowColors() {
		$('#playlist tr:even').addClass('alt');
	}
	
	function togglePlaylistPaneVisibility(){
        $('#main').toggleClass('use-sidebar');
        
        var hasSidebar = $('#main').hasClass('use-sidebar') + '';
        $.cookie("show_playlist_sidebar", hasSidebar);
    }
	
	function createPlaylistListReloader() {
	    // create double click handler for playlist
	    installClickHandlers('.playlist_item', handlePlaylistClicked, playPlaylist);
	    
	    // create playlist list reloader
	    // TODO - turn this on once the track list reloads via ajax
	    //setInterval(reloadPlaylists, 30000);
        reloadPlaylists();
	}
	
	function playPlaylist(event) {
	    var div = $(event.currentTarget),
			requestedPlaylist = $(event.currentTarget).html();
        
        post({'action':'play-playlist', 'playlist': requestedPlaylist}, true);
	}
	
	function reloadPlaylists() {
	   // ajax load of playlists
	   $.get('/playlists',displayPlaylists);
	}
	
	function displayPlaylists(playlistData) {
		// display the new playlists
		var playlistHTMLs = '',
		// add play queue
		playQueueEl = '<div class="playlist_item playqueue';
		if (playlistData.selected == 'Play Queue') {
			playQueueEl += ' selected';
		}
		playQueueEl += '"	>Play Queue</div>';

		playlistHTMLs += playQueueEl;
		
		for (var i in playlistData.playlists) {
			var div = '<div class="playlist_item';
			if (playlistData.selected === playlistData.playlists[i]) {
				div += ' selected';
			}
			div += '">' + playlistData.playlists[i] + '</div>';
			playlistHTMLs += div;
		}
	
		// reload playlist content
		playlistBoxEl.html(playlistHTMLs);
	}
	
	function loadCurrentPlayingSong() {
		services.getCurrent().done(function(data) {
			var incomingTitle = data.title;
			if (incomingTitle !== '') {
				$('#playing').html('<cite id="title">' + incomingTitle + '</cite> by <cite id="artist">' + data.artist + '</cite> from <cite id="album">' +
					data.album + '</cite> <cite id="stream">' + data.stream + '</cite>' );
				$(document).attr('title', incomingTitle);
			} else {
				$('#playing').html('<span id="not-playing">Not playing</span>');
				$(document).attr('title', 'Rhythmweb');
			}
		}, 'json');
	}
	
	function loadInitialPlayList() {
		loadPlaylistSlice(0, sliceStep);//loading in parts with prevent browser and rb from freezing for large lists
	}
	
	function loadPlaylistSlice(start, end) {
		services.getSlice({'start': start, 'end': end}).done(function(data) {
			var playlist = '';
			$(data.tracks).each(function (i, item) {
				playlist += '<tr id="' + item.id + '"><td>' + item.title + '</td><td>' + item.artist + '</td><td>' + item.album + '</td></tr>';
			});
			
			var playlistTable = $('#playlist');
			
			if (start === 0) {
				playlistTable.append('<tbody>');
			}
			
			playlistTable.append(playlist);
			
			if (data.tracks.length === sliceStep) {
				setTimeout(loadPlaylistSlice(end, end += sliceStep), 500);
			} else {
				playlistTable.append('</tbody>');
				$('#loading').hide();
			}
		});
	}
	
	function initialize() {
		loadInitialPlayList();

        var playlistViewCookie = $.cookie("show_playlist_sidebar"),
        	playBtn = $('#play');
        if (playlistViewCookie !== null && playlistViewCookie === "true") {
            $('#main').addClass('use-sidebar');
        }
		
		playBtn.click(play);
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
		setPlaybutton(playBtn.attr("isplaying").toLowerCase() === "true");

		//refresh currently playing song from server every 10s (no worries it takes about 12ms)
		setInterval(loadCurrentPlayingSong, 10000);
	}

	initialize();
}

$(function() {
	new Rhythmweb();
});