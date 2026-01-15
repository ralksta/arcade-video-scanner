/**
 * Timeline Scrubber Component
 * Visual timeline with draggable handles for trim point selection
 */

class TimelineScrubber {
    constructor(videoElement, options = {}) {
        this.video = videoElement;
        this.container = null;
        this.track = null;
        this.handleStart = null;
        this.handleEnd = null;
        this.selection = null;
        this.playhead = null;

        // State
        this.duration = 0;
        this.startTime = 0;
        this.endTime = 0;
        this.isDragging = false;
        this.activeHandle = null;

        // Options
        this.options = {
            containerSelector: options.containerSelector || '#timelineScrubber',
            onChange: options.onChange || (() => { }),
            minDuration: options.minDuration || 0.5, // Minimum 0.5 seconds
            ...options
        };

        // Bind methods
        this.handleMouseDown = this.handleMouseDown.bind(this);
        this.handleMouseMove = this.handleMouseMove.bind(this);
        this.handleMouseUp = this.handleMouseUp.bind(this);
        this.handleTimeUpdate = this.handleTimeUpdate.bind(this);
        this.handleClick = this.handleClick.bind(this);
    }

    /**
     * Initialize the timeline scrubber
     */
    init() {
        this.container = document.querySelector(this.options.containerSelector);
        if (!this.container) {
            console.error('Timeline container not found:', this.options.containerSelector);
            return;
        }

        // Wait for video metadata if not loaded
        if (!this.video.duration || this.video.duration === 0) {
            this.video.addEventListener('loadedmetadata', () => {
                this.duration = this.video.duration || 10;
                this.endTime = this.duration;
                this.render();
                this.attachEventListeners();
            }, { once: true });
        } else {
            this.duration = this.video.duration;
            this.endTime = this.duration;
            this.render();
            this.attachEventListeners();
        }

        return this;
    }

    /**
     * Render the timeline HTML structure
     */
    render() {


        this.container.innerHTML = `
            <div class="timeline-scrubber">
                <div class="timeline-track" id="timelineTrack">
                    <canvas class="timeline-thumbnails" id="timelineThumbnails"></canvas>
                    <div class="timeline-selection" id="timelineSelection"></div>
                    <div class="timeline-handle timeline-handle-start" id="handleStart" data-handle="start">
                        <div class="timeline-handle-inner"></div>
                        <div class="timeline-tooltip" id="tooltipStart">00:00</div>
                    </div>
                    <div class="timeline-handle timeline-handle-end" id="handleEnd" data-handle="end">
                        <div class="timeline-handle-inner"></div>
                        <div class="timeline-tooltip" id="tooltipEnd">00:00</div>
                    </div>
                    <div class="timeline-playhead" id="timelinePlayhead"></div>
                </div>
                <div class="timeline-labels">
                    <span class="timeline-label-start">0:00</span>
                    <span class="timeline-label-end">${this.formatTime(this.duration)}</span>
                </div>
            </div>
        `;


        // Get element references
        this.track = document.getElementById('timelineTrack');
        this.handleStart = document.getElementById('handleStart');
        this.handleEnd = document.getElementById('handleEnd');
        this.selection = document.getElementById('timelineSelection');
        this.playhead = document.getElementById('timelinePlayhead');


        // Initial positions
        this.updateHandlePositions();

        // Generate thumbnails
        this.generateThumbnails();

    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Handle dragging
        this.handleStart.addEventListener('mousedown', this.handleMouseDown);
        this.handleEnd.addEventListener('mousedown', this.handleMouseDown);

        // Track clicking
        this.track.addEventListener('click', this.handleClick);

        // Video time updates
        this.video.addEventListener('timeupdate', this.handleTimeUpdate);

        // Global mouse events (for dragging)
        document.addEventListener('mousemove', this.handleMouseMove);
        document.addEventListener('mouseup', this.handleMouseUp);
    }

    /**
     * Handle mouse down on handle
     */
    handleMouseDown(e) {
        e.preventDefault();
        e.stopPropagation();

        this.isDragging = true;
        this.activeHandle = e.currentTarget.dataset.handle;
        this.track.classList.add('dragging');
        e.currentTarget.classList.add('active');

        // Pause video while scrubbing
        this.wasPlaying = !this.video.paused;
        this.video.pause();
    }

    /**
     * Handle mouse move during drag
     */
    handleMouseMove(e) {
        if (!this.isDragging || !this.activeHandle) return;

        const rect = this.track.getBoundingClientRect();
        const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
        const percentage = x / rect.width;
        const time = percentage * this.duration;

        // Update time based on which handle is being dragged
        let newTime;
        if (this.activeHandle === 'start') {
            // Ensure start doesn't exceed end - minDuration
            this.startTime = Math.min(time, this.endTime - this.options.minDuration);
            newTime = this.startTime;
        } else {
            // Ensure end doesn't go before start + minDuration
            this.endTime = Math.max(time, this.startTime + this.options.minDuration);
            newTime = this.endTime;
        }

        this.updateHandlePositions();
        this.notifyChange();

        // Scrub video to current handle position (throttled slightly by browser frame rate)
        this.video.currentTime = newTime;
    }

    /**
     * Handle mouse up (end drag)
     */
    handleMouseUp(e) {
        if (!this.isDragging) return;

        this.isDragging = false;
        this.track.classList.remove('dragging');

        if (this.activeHandle) {
            const handle = this.activeHandle === 'start' ? this.handleStart : this.handleEnd;
            handle.classList.remove('active');
            this.activeHandle = null;
        }
    }

    /**
     * Handle click on timeline track (seek video)
     */
    handleClick(e) {
        if (e.target.classList.contains('timeline-handle') ||
            e.target.closest('.timeline-handle')) {
            return; // Don't seek if clicking on handle
        }

        const rect = this.track.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = x / rect.width;
        const time = percentage * this.duration;

        // Seek video to clicked position
        this.video.currentTime = time;
    }

    /**
     * Handle video time update (update playhead)
     */
    handleTimeUpdate() {
        if (!this.playhead) return; // Allow update while dragging to follow scrub

        const percentage = (this.video.currentTime / this.duration) * 100;
        this.playhead.style.left = `${percentage}%`;
    }

    /**
     * Update handle positions based on current times
     */
    updateHandlePositions() {
        const startPercentage = (this.startTime / this.duration) * 100;
        const endPercentage = (this.endTime / this.duration) * 100;

        // Position handles
        this.handleStart.style.left = `${startPercentage}%`;
        this.handleEnd.style.left = `${endPercentage}%`;

        // Update selection overlay
        this.selection.style.left = `${startPercentage}%`;
        this.selection.style.width = `${endPercentage - startPercentage}%`;

        // Update tooltips
        const tooltipStart = this.handleStart.querySelector('.timeline-tooltip');
        const tooltipEnd = this.handleEnd.querySelector('.timeline-tooltip');

        if (tooltipStart) tooltipStart.textContent = this.formatTime(this.startTime);
        if (tooltipEnd) tooltipEnd.textContent = this.formatTime(this.endTime);
    }

    /**
     * Generate thumbnails for the background
     */
    async generateThumbnails() {
        if (this.generatingThumbnails) return;
        this.generatingThumbnails = true;

        const canvas = document.getElementById('timelineThumbnails');
        // Use currentSrc if src is empty (e.g. source element used)
        const videoSrc = this.video.currentSrc || this.video.src;

        if (!canvas || !videoSrc) {
            console.log('Timeline: Cannot generate thumbnails, missing canvas or src');
            this.generatingThumbnails = false;
            return;
        }

        const ctx = canvas.getContext('2d');
        const rect = this.track.getBoundingClientRect();

        // Set canvas size to match visual size (for generic high dpi support we could multiple by devicePixelRatio)
        canvas.width = rect.width;
        canvas.height = rect.height;

        // Clear canvas
        ctx.fillStyle = '#1a1a24'; // Match background
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Create hidden video for capturing
        const videoClone = document.createElement('video');
        videoClone.src = videoSrc;
        videoClone.crossOrigin = "anonymous"; // Handle CORS if needed
        videoClone.muted = true;
        videoClone.currentTime = 0;

        // Wait for metadata to get dimensions
        try {
            await new Promise((resolve, reject) => {
                videoClone.onloadedmetadata = resolve;
                videoClone.onerror = reject;
                setTimeout(() => reject('Timeout loading metadata'), 5000);
            });

            const thumbHeight = canvas.height;
            const aspectRatio = videoClone.videoWidth / videoClone.videoHeight;
            const thumbWidth = thumbHeight * aspectRatio;
            const count = Math.ceil(canvas.width / thumbWidth);
            const interval = this.duration / count;

            // Draw loop
            for (let i = 0; i < count; i++) {
                // Stop if destroyed
                if (!this.container) break;

                const time = i * interval;
                videoClone.currentTime = time;

                await new Promise((resolve) => {
                    const onSeeked = () => {
                        resolve();
                    };
                    videoClone.onseeked = onSeeked;
                    // Timeout fallback
                    setTimeout(resolve, 200);
                });

                ctx.drawImage(videoClone, i * thumbWidth, 0, thumbWidth, thumbHeight);

                // Small delay to yield to UI thread
                if (i % 5 === 0) await new Promise(r => setTimeout(r, 0));
            }
        } catch (e) {
            console.error('Timeline: Error generating thumbnails', e);
        } finally {
            // Cleanup
            videoClone.src = '';
            videoClone.remove();
            this.generatingThumbnails = false;
        }
    }

    /**
     * Notify onChange callback
     */
    notifyChange() {
        this.options.onChange({
            startTime: this.startTime,
            endTime: this.endTime,
            duration: this.endTime - this.startTime
        });
    }

    /**
     * Set trim times programmatically
     */
    setTimes(startTime, endTime) {
        this.startTime = Math.max(0, Math.min(startTime, this.duration));
        this.endTime = Math.max(this.startTime + this.options.minDuration, Math.min(endTime, this.duration));
        this.updateHandlePositions();
        this.notifyChange();
    }

    /**
     * Get current trim times
     */
    getTimes() {
        return {
            startTime: this.startTime,
            endTime: this.endTime,
            duration: this.endTime - this.startTime
        };
    }

    /**
     * Format time in MM:SS or HH:MM:SS
     */
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Destroy the timeline scrubber
     */
    destroy() {
        // Remove event listeners
        if (this.handleStart) {
            this.handleStart.removeEventListener('mousedown', this.handleMouseDown);
        }
        if (this.handleEnd) {
            this.handleEnd.removeEventListener('mousedown', this.handleMouseDown);
        }
        if (this.track) {
            this.track.removeEventListener('click', this.handleClick);
        }
        if (this.video) {
            this.video.removeEventListener('timeupdate', this.handleTimeUpdate);
        }

        document.removeEventListener('mousemove', this.handleMouseMove);
        document.removeEventListener('mouseup', this.handleMouseUp);

        // Clear container
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

/**
 * Helper function to format time for input fields (MM:SS or HH:MM:SS)
 */
function formatTimeForInput(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Export for use in other modules
window.TimelineScrubber = TimelineScrubber;
window.formatTimeForInput = formatTimeForInput;
