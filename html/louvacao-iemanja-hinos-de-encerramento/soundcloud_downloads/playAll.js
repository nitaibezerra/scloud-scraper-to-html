(function () {
    let currentIndex = 0;
    const player = document.getElementById('playerAll');

    // Called when user clicks "Play All" button
    window.playAll = function () {
        if (!window.allTracks || window.allTracks.length === 0) {
            return;
        }
        currentIndex = 0;
        player.src = window.allTracks[currentIndex];
        player.play();
    };

    // Event listener that automatically plays the next track when one ends
    player.addEventListener('ended', function () {
        currentIndex++;
        if (window.allTracks && currentIndex < window.allTracks.length) {
            player.src = window.allTracks[currentIndex];
            player.play();
        }
    });
})();