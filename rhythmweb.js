function Rhythmweb() {
	
	var toggleShuffleEl;
	var toggleRepeatEl;
	
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
		post({'action':'play'}, true);
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
	
	var initialize = function() {
		toggleShuffleEl = $('#toggle-shuffle');
		toggleRepeatEl = $('#toggle-repeat');
		
		$('#play').click(play);
		$('#previous-track').click(previousTrack);
		$('#next-track').click(nextTrack);
		$('#volume-up').click(volumeUp);
		$('#volume-down').click(volumeDown);
		toggleShuffleEl.click(toggleShuffle);
		toggleRepeatEl.click(toggleRepeat);
	};

	initialize();
}


$(document).ready(function() {
	new Rhythmweb();
});
