/**
 * VR Museum — Arcade Gallery
 * Immersive WebXR gallery for Meta Quest 3
 * 
 * Architecture:
 *  - Fetches /api/vr/gallery for room/video data
 *  - Procedurally builds gallery rooms per collection
 *  - Rooms are connected via portals (teleport on click)
 *  - Videos displayed as framed thumbnails on walls
 *  - Click thumbnail → floating video player
 */

(function () {
    'use strict';

    // ======================== CONSTANTS ========================
    const ROOM_WIDTH = 14;
    const ROOM_DEPTH = 14;
    const ROOM_HEIGHT = 4.5;
    const FRAMES_PER_WALL = 4;
    const FRAME_WIDTH = 2.4;
    const FRAME_HEIGHT = 1.6;
    const FRAME_PADDING = 0.15;
    const FRAME_Y = 2.0;
    const WALL_THICKNESS = 0.12;

    // Colors (dark erotic leather palette)
    const C = {
        wallBase: '#0e0808',
        wallAccent: '#1a0c0c',
        floor: '#0d0706',
        ceiling: '#080404',
        frameBorder: '#b87333',   // Antique bronze
        frameInner: '#1c0f0f',
        portalFrame: '#8b4513',
        portalGlow: '#ff3366',
        textColor: '#d4a574',
        spotWarm: '#ff9966',
        spotAccent: '#ff3366',
        leather: '#2a1215',
        trimStrip: '#4a1a1a',
    };

    // ======================== STATE ========================
    let galleryData = null;
    let currentRoomIndex = 0;
    let activeVideo = null;

    // ======================== BOOT ========================
    document.addEventListener('DOMContentLoaded', init);

    async function init() {
        setStatus('Connecting to library…');
        try {
            const resp = await fetch('/api/vr/gallery');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            galleryData = await resp.json();
        } catch (err) {
            setStatus('Failed to load gallery: ' + err.message);
            console.error(err);
            return;
        }

        if (!galleryData.rooms || galleryData.rooms.length === 0) {
            setStatus('No collections found. Add smart collections in Settings.');
            return;
        }

        setStatus(`Building ${galleryData.rooms.length} gallery rooms…`);

        // Wait for A-Frame scene to be ready
        const scene = document.getElementById('vr-scene');
        if (scene.hasLoaded) {
            buildGallery();
        } else {
            scene.addEventListener('loaded', buildGallery);
        }
    }

    // ======================== GALLERY BUILDER ========================
    function buildGallery() {
        const root = document.getElementById('gallery-root');
        const rooms = galleryData.rooms;

        // Build lobby
        buildLobby(root, rooms);

        // Build each collection room
        rooms.forEach((room, i) => {
            const roomOffset = getRoomPosition(i + 1); // room 0 = lobby
            buildRoom(root, room, i, roomOffset);
        });

        // Position camera in lobby
        const rig = document.getElementById('camera-rig');
        rig.setAttribute('position', '0 0 0');

        // Hide loading
        setTimeout(() => {
            document.getElementById('loading-overlay').classList.add('hidden');
            showRoomHud('Lobby');
        }, 600);

        // Wire up video player close
        document.getElementById('player-close').addEventListener('click', closeVideoPlayer);
    }

    /**
     * Calculate room position in a linear hallway layout.
     * Rooms are placed along the -Z axis, spaced apart.
     */
    function getRoomPosition(index) {
        return { x: 0, y: 0, z: -(index * (ROOM_DEPTH + 4)) };
    }

    // ======================== LOBBY ========================
    function buildLobby(parent, rooms) {
        const lobby = document.createElement('a-entity');
        lobby.setAttribute('id', 'room-lobby');
        lobby.setAttribute('position', '0 0 0');

        // Scale lobby width based on portal count (min 14, ~4m per portal)
        const portalCount = rooms.length;
        const lobbyWidth = Math.max(ROOM_WIDTH, portalCount * 4);
        const lobbyDepth = ROOM_DEPTH;

        // Floor
        addPlane(lobby, {
            w: lobbyWidth, h: lobbyDepth,
            pos: `0 0.01 0`, rot: '-90 0 0',
            color: C.floor, roughness: 0.7, metalness: 0.2
        });

        // Ceiling
        addPlane(lobby, {
            w: lobbyWidth, h: lobbyDepth,
            pos: `0 ${ROOM_HEIGHT} 0`, rot: '90 0 0',
            color: C.ceiling, roughness: 0.9
        });

        // Walls (left, right, back)
        // Back wall (behind spawn)
        addWall(lobby, {
            w: lobbyWidth, h: ROOM_HEIGHT,
            pos: `0 ${ROOM_HEIGHT / 2} ${lobbyDepth / 2}`,
            rot: '0 0 0'
        });

        // Left wall
        addWall(lobby, {
            w: lobbyDepth, h: ROOM_HEIGHT,
            pos: `${-lobbyWidth / 2} ${ROOM_HEIGHT / 2} 0`,
            rot: '0 90 0'
        });

        // Right wall  
        addWall(lobby, {
            w: lobbyDepth, h: ROOM_HEIGHT,
            pos: `${lobbyWidth / 2} ${ROOM_HEIGHT / 2} 0`,
            rot: '0 -90 0'
        });

        // Lobby title
        addText(lobby, {
            value: 'ARCADE GALLERY',
            pos: `0 ${ROOM_HEIGHT - 0.6} ${lobbyDepth / 2 - 0.2}`,
            rot: '0 180 0',
            scale: '6 6 6',
            color: C.frameBorder
        });

        // Leather trim strip along bottom of back wall
        addPlane(lobby, {
            w: lobbyWidth, h: 0.4,
            pos: `0 0.2 ${lobbyDepth / 2 - 0.06}`,
            rot: '0 180 0',
            color: C.trimStrip, roughness: 0.4, metalness: 0.3
        });

        // Ambient spot in lobby
        const lobbyLight = document.createElement('a-light');
        lobbyLight.setAttribute('type', 'point');
        lobbyLight.setAttribute('color', C.spotWarm);
        lobbyLight.setAttribute('intensity', '0.6');
        lobbyLight.setAttribute('distance', String(lobbyWidth));
        lobbyLight.setAttribute('position', `0 ${ROOM_HEIGHT - 0.5} 0`);
        lobby.appendChild(lobbyLight);

        // Portal doors to each room — spaced evenly across the front wall
        const spacing = lobbyWidth / (portalCount + 1);

        rooms.forEach((room, i) => {
            const px = -lobbyWidth / 2 + spacing * (i + 1);
            const pz = -lobbyDepth / 2;
            buildPortal(lobby, room.name, i, px, pz, '0 0 0');
        });

        parent.appendChild(lobby);
    }

    // ======================== ROOM ========================
    function buildRoom(parent, roomData, roomIndex, offset) {
        const room = document.createElement('a-entity');
        room.setAttribute('id', `room-${roomIndex}`);
        room.setAttribute('position', `${offset.x} ${offset.y} ${offset.z}`);

        // Floor
        addPlane(room, {
            w: ROOM_WIDTH, h: ROOM_DEPTH,
            pos: '0 0.01 0', rot: '-90 0 0',
            color: C.floor, roughness: 0.6, metalness: 0.15
        });

        // Ceiling
        addPlane(room, {
            w: ROOM_WIDTH, h: ROOM_DEPTH,
            pos: `0 ${ROOM_HEIGHT} 0`, rot: '90 0 0',
            color: C.ceiling, roughness: 0.9
        });

        // Room title on back wall
        addText(room, {
            value: roomData.name.toUpperCase(),
            pos: `0 ${ROOM_HEIGHT - 0.6} ${ROOM_DEPTH / 2 - 0.2}`,
            rot: '0 180 0',
            scale: '5 5 5',
            color: C.frameBorder
        });

        // Leather trim strips (top and bottom of walls)
        // Bottom trim - all walls
        addPlane(room, {
            w: ROOM_WIDTH, h: 0.25,
            pos: `0 0.13 ${ROOM_DEPTH / 2 - 0.06}`,
            rot: '0 180 0',
            color: C.leather, roughness: 0.35, metalness: 0.2
        });
        addPlane(room, {
            w: ROOM_WIDTH, h: 0.25,
            pos: `0 0.13 ${-ROOM_DEPTH / 2 + 0.06}`,
            rot: '0 0 0',
            color: C.leather, roughness: 0.35, metalness: 0.2
        });

        // Build walls and place video frames
        const videos = roomData.videos || [];
        const walls = distributeToWalls(videos);

        // Back wall (looking from entrance)
        addWall(room, {
            w: ROOM_WIDTH, h: ROOM_HEIGHT,
            pos: `0 ${ROOM_HEIGHT / 2} ${ROOM_DEPTH / 2}`,
            rot: '0 0 0'
        });
        placeFramesOnWall(room, walls.back, {
            wallCenter: [0, FRAME_Y, ROOM_DEPTH / 2 - 0.08],
            facing: [0, 180, 0],
            maxFrames: FRAMES_PER_WALL
        }, roomIndex);

        // Left wall
        addWall(room, {
            w: ROOM_DEPTH, h: ROOM_HEIGHT,
            pos: `${-ROOM_WIDTH / 2} ${ROOM_HEIGHT / 2} 0`,
            rot: '0 90 0'
        });
        placeFramesOnWall(room, walls.left, {
            wallCenter: [-ROOM_WIDTH / 2 + 0.08, FRAME_Y, 0],
            facing: [0, 90, 0],
            maxFrames: FRAMES_PER_WALL,
            axis: 'z'
        }, roomIndex);

        // Right wall
        addWall(room, {
            w: ROOM_DEPTH, h: ROOM_HEIGHT,
            pos: `${ROOM_WIDTH / 2} ${ROOM_HEIGHT / 2} 0`,
            rot: '0 -90 0'
        });
        placeFramesOnWall(room, walls.right, {
            wallCenter: [ROOM_WIDTH / 2 - 0.08, FRAME_Y, 0],
            facing: [0, -90, 0],
            maxFrames: FRAMES_PER_WALL,
            axis: 'z'
        }, roomIndex);

        // Front wall (with doorway gap)
        // Left portion
        addWall(room, {
            w: (ROOM_WIDTH - 2.5) / 2, h: ROOM_HEIGHT,
            pos: `${-(ROOM_WIDTH / 4 + 0.625)} ${ROOM_HEIGHT / 2} ${-ROOM_DEPTH / 2}`,
            rot: '0 180 0'
        });
        // Right portion
        addWall(room, {
            w: (ROOM_WIDTH - 2.5) / 2, h: ROOM_HEIGHT,
            pos: `${(ROOM_WIDTH / 4 + 0.625)} ${ROOM_HEIGHT / 2} ${-ROOM_DEPTH / 2}`,
            rot: '0 180 0'
        });
        // Top portion above doorway
        addWall(room, {
            w: 2.5, h: ROOM_HEIGHT - 2.8,
            pos: `0 ${2.8 + (ROOM_HEIGHT - 2.8) / 2} ${-ROOM_DEPTH / 2}`,
            rot: '0 180 0'
        });
        placeFramesOnWall(room, walls.front, {
            wallCenter: [0, FRAME_Y, -ROOM_DEPTH / 2 + 0.08],
            facing: [0, 0, 0],
            maxFrames: 2, // Less space due to doorway
        }, roomIndex);

        // Room lighting (spotlights for each frame)
        const mainLight = document.createElement('a-light');
        mainLight.setAttribute('type', 'point');
        mainLight.setAttribute('color', C.spotWarm);
        mainLight.setAttribute('intensity', '0.5');
        mainLight.setAttribute('distance', '18');
        mainLight.setAttribute('position', `0 ${ROOM_HEIGHT - 0.3} 0`);
        room.appendChild(mainLight);

        // Accent spot (subtle pink)
        const accentLight = document.createElement('a-light');
        accentLight.setAttribute('type', 'point');
        accentLight.setAttribute('color', C.spotAccent);
        accentLight.setAttribute('intensity', '0.15');
        accentLight.setAttribute('distance', '12');
        accentLight.setAttribute('position', `${ROOM_WIDTH / 3} ${ROOM_HEIGHT - 0.5} ${ROOM_DEPTH / 4}`);
        room.appendChild(accentLight);

        // Return portal (back to lobby)
        buildPortal(room, '← Lobby', -1, 0, -ROOM_DEPTH / 2, '0 180 0', true);

        parent.appendChild(room);
    }

    // ======================== WALL HELPERS ========================

    function addWall(parent, opts) {
        const el = document.createElement('a-plane');
        el.setAttribute('width', opts.w);
        el.setAttribute('height', opts.h);
        el.setAttribute('position', opts.pos);
        el.setAttribute('rotation', opts.rot);
        el.setAttribute('material', `color: ${C.wallBase}; roughness: 0.85; metalness: 0.05; side: double`);
        parent.appendChild(el);
        return el;
    }

    function addPlane(parent, opts) {
        const el = document.createElement('a-plane');
        el.setAttribute('width', opts.w);
        el.setAttribute('height', opts.h);
        el.setAttribute('position', opts.pos);
        el.setAttribute('rotation', opts.rot);
        const mat = `color: ${opts.color}; roughness: ${opts.roughness || 0.8}; metalness: ${opts.metalness || 0}; side: double`;
        el.setAttribute('material', mat);
        parent.appendChild(el);
        return el;
    }

    function addText(parent, opts) {
        const el = document.createElement('a-text');
        el.setAttribute('value', opts.value);
        el.setAttribute('position', opts.pos);
        el.setAttribute('rotation', opts.rot);
        el.setAttribute('scale', opts.scale || '3 3 3');
        el.setAttribute('color', opts.color || C.textColor);
        el.setAttribute('align', 'center');
        el.setAttribute('font', 'mozillavr');
        el.setAttribute('anchor', 'center');
        parent.appendChild(el);
        return el;
    }

    // ======================== VIDEO FRAMES ========================

    /**
     * Distribute videos across 4 walls: back, left, right, front
     */
    function distributeToWalls(videos) {
        const walls = { back: [], left: [], right: [], front: [] };
        const order = ['back', 'left', 'right', 'front'];
        const limits = [FRAMES_PER_WALL, FRAMES_PER_WALL, FRAMES_PER_WALL, 2];

        let vi = 0;
        for (let w = 0; w < order.length && vi < videos.length; w++) {
            for (let f = 0; f < limits[w] && vi < videos.length; f++) {
                walls[order[w]].push(videos[vi++]);
            }
        }
        return walls;
    }

    /**
     * Place frames along a wall surface.
     */
    function placeFramesOnWall(parent, videos, opts, roomIndex) {
        if (!videos.length) return;

        const count = Math.min(videos.length, opts.maxFrames);
        const totalWidth = count * FRAME_WIDTH + (count - 1) * 0.6;
        const startOffset = -totalWidth / 2 + FRAME_WIDTH / 2;
        const axis = opts.axis || 'x'; // Which axis to spread along

        videos.forEach((video, i) => {
            if (i >= opts.maxFrames) return;

            const offset = startOffset + i * (FRAME_WIDTH + 0.6);
            let pos;
            if (axis === 'x') {
                pos = [
                    opts.wallCenter[0] + offset,
                    opts.wallCenter[1],
                    opts.wallCenter[2]
                ];
            } else {
                pos = [
                    opts.wallCenter[0],
                    opts.wallCenter[1],
                    opts.wallCenter[2] + offset
                ];
            }

            buildVideoFrame(parent, video, pos, opts.facing, `r${roomIndex}_f${i}`);
        });
    }

    /**
     * Build a single framed video thumbnail.
     */
    function buildVideoFrame(parent, video, pos, rot, id) {
        const frame = document.createElement('a-entity');
        frame.setAttribute('position', pos.join(' '));
        frame.setAttribute('rotation', rot.join(' '));

        // Outer frame (bronze border)
        const border = document.createElement('a-plane');
        border.setAttribute('width', FRAME_WIDTH + FRAME_PADDING * 2);
        border.setAttribute('height', FRAME_HEIGHT + FRAME_PADDING * 2);
        border.setAttribute('material', `color: ${C.frameBorder}; roughness: 0.3; metalness: 0.7`);
        border.setAttribute('position', '0 0 -0.02');
        frame.appendChild(border);

        // Inner matte (dark leather inset)
        const matte = document.createElement('a-plane');
        matte.setAttribute('width', FRAME_WIDTH + 0.06);
        matte.setAttribute('height', FRAME_HEIGHT + 0.06);
        matte.setAttribute('material', `color: ${C.frameInner}; roughness: 0.6; metalness: 0.1`);
        matte.setAttribute('position', '0 0 -0.01');
        frame.appendChild(matte);

        // Thumbnail image
        const thumb = document.createElement('a-plane');
        thumb.setAttribute('width', FRAME_WIDTH);
        thumb.setAttribute('height', FRAME_HEIGHT);
        thumb.setAttribute('class', 'clickable');
        thumb.setAttribute('id', `frame-${id}`);

        if (video.thumbnail) {
            thumb.setAttribute('material', `src: url(${video.thumbnail}); roughness: 0.5; metalness: 0.0; shader: flat`);
        } else {
            thumb.setAttribute('material', `color: ${C.wallAccent}; shader: flat`);
        }

        // Store video data for click handler
        thumb.dataset.streamUrl = video.stream_url || '';
        thumb.dataset.title = video.title || '';

        thumb.addEventListener('click', function () {
            openVideoPlayer(this.dataset.streamUrl, this.dataset.title);
        });

        // Hover effect
        thumb.addEventListener('mouseenter', function () {
            border.setAttribute('material', 'emissive', '#ff3366');
            border.setAttribute('material', 'emissiveIntensity', '0.3');
        });
        thumb.addEventListener('mouseleave', function () {
            border.setAttribute('material', 'emissive', '#000000');
            border.setAttribute('material', 'emissiveIntensity', '0');
        });

        frame.appendChild(thumb);

        // Title label below frame
        if (video.title) {
            const label = document.createElement('a-text');
            label.setAttribute('value', truncate(video.title, 28));
            label.setAttribute('position', `0 ${-(FRAME_HEIGHT / 2 + 0.25)} 0.01`);
            label.setAttribute('align', 'center');
            label.setAttribute('color', C.textColor);
            label.setAttribute('scale', '1.6 1.6 1.6');
            label.setAttribute('font', 'mozillavr');
            frame.appendChild(label);

            // Duration badge
            if (video.duration) {
                const dur = document.createElement('a-text');
                dur.setAttribute('value', formatDuration(video.duration));
                dur.setAttribute('position', `${FRAME_WIDTH / 2 - 0.15} ${FRAME_HEIGHT / 2 - 0.15} 0.01`);
                dur.setAttribute('align', 'right');
                dur.setAttribute('color', '#ffffff');
                dur.setAttribute('scale', '1.2 1.2 1.2');
                dur.setAttribute('font', 'mozillavr');
                frame.appendChild(dur);
            }
        }

        // Spotlight for this frame
        const spot = document.createElement('a-light');
        spot.setAttribute('type', 'spot');
        spot.setAttribute('color', C.spotWarm);
        spot.setAttribute('intensity', '0.5');
        spot.setAttribute('angle', '35');
        spot.setAttribute('penumbra', '0.6');
        spot.setAttribute('distance', '6');
        spot.setAttribute('position', '0 2 1.5');
        spot.setAttribute('target', `#frame-${id}`);
        frame.appendChild(spot);

        parent.appendChild(frame);
    }

    // ======================== PORTALS ========================

    function buildPortal(parent, label, targetIndex, x, z, rot, isReturn) {
        const portal = document.createElement('a-entity');
        portal.setAttribute('position', `${x} 0 ${z}`);
        portal.setAttribute('rotation', rot);

        // Portal frame (archway) — compact 1.6m wide
        const archHalfW = 0.8;
        const archLeft = document.createElement('a-box');
        archLeft.setAttribute('width', '0.12');
        archLeft.setAttribute('height', '2.6');
        archLeft.setAttribute('depth', '0.12');
        archLeft.setAttribute('position', `${-archHalfW} 1.3 0`);
        archLeft.setAttribute('material', `color: ${C.portalFrame}; roughness: 0.4; metalness: 0.5`);
        portal.appendChild(archLeft);

        const archRight = document.createElement('a-box');
        archRight.setAttribute('width', '0.12');
        archRight.setAttribute('height', '2.6');
        archRight.setAttribute('depth', '0.12');
        archRight.setAttribute('position', `${archHalfW} 1.3 0`);
        archRight.setAttribute('material', `color: ${C.portalFrame}; roughness: 0.4; metalness: 0.5`);
        portal.appendChild(archRight);

        const archTop = document.createElement('a-box');
        archTop.setAttribute('width', String(archHalfW * 2 + 0.12));
        archTop.setAttribute('height', '0.12');
        archTop.setAttribute('depth', '0.12');
        archTop.setAttribute('position', '0 2.66 0');
        archTop.setAttribute('material', `color: ${C.portalFrame}; roughness: 0.4; metalness: 0.5`);
        portal.appendChild(archTop);

        // Glowing portal plane (clickable)
        const portalPlane = document.createElement('a-plane');
        portalPlane.setAttribute('width', String(archHalfW * 2 - 0.1));
        portalPlane.setAttribute('height', '2.5');
        portalPlane.setAttribute('position', '0 1.3 0');
        portalPlane.setAttribute('class', 'clickable');
        portalPlane.setAttribute('material', `color: ${C.portalGlow}; opacity: 0.12; shader: flat; side: double`);
        portalPlane.dataset.targetRoom = String(targetIndex);
        portalPlane.addEventListener('click', function () {
            teleportToRoom(parseInt(this.dataset.targetRoom));
        });
        portalPlane.addEventListener('mouseenter', function () {
            this.setAttribute('material', 'opacity', '0.3');
        });
        portalPlane.addEventListener('mouseleave', function () {
            this.setAttribute('material', 'opacity', '0.12');
        });
        portal.appendChild(portalPlane);

        // Label above portal — small, constrained width
        const text = document.createElement('a-text');
        text.setAttribute('value', truncate(label.toUpperCase(), 16));
        text.setAttribute('position', '0 2.95 0');
        text.setAttribute('align', 'center');
        text.setAttribute('color', isReturn ? '#ff6699' : C.textColor);
        text.setAttribute('scale', '1.6 1.6 1.6');
        text.setAttribute('font', 'mozillavr');
        text.setAttribute('side', 'double');
        text.setAttribute('wrapCount', '20');
        text.setAttribute('width', '3');
        portal.appendChild(text);

        // Glow light at portal
        const glow = document.createElement('a-light');
        glow.setAttribute('type', 'point');
        glow.setAttribute('color', C.portalGlow);
        glow.setAttribute('intensity', '0.25');
        glow.setAttribute('distance', '4');
        glow.setAttribute('position', '0 1.3 0.4');
        portal.appendChild(glow);

        parent.appendChild(portal);
    }

    // ======================== TELEPORTATION ========================

    function teleportToRoom(roomIndex) {
        const rig = document.getElementById('camera-rig');

        if (roomIndex === -1) {
            // Back to lobby
            rig.setAttribute('position', '0 0 0');
            currentRoomIndex = -1;
            showRoomHud('Lobby');
        } else {
            const targetPos = getRoomPosition(roomIndex + 1);
            rig.setAttribute('position', `${targetPos.x} ${targetPos.y} ${targetPos.z + ROOM_DEPTH / 2 - 2}`);
            currentRoomIndex = roomIndex;
            showRoomHud(galleryData.rooms[roomIndex].name);
        }
    }

    // ======================== VIDEO PLAYER ========================

    function openVideoPlayer(streamUrl, title) {
        if (!streamUrl) return;

        const player = document.getElementById('video-player');
        const screen = document.getElementById('player-screen');

        // Remove old video element if any
        const oldVid = document.getElementById('vr-active-video');
        if (oldVid) oldVid.remove();

        // Create video element dynamically
        const videoEl = document.createElement('video');
        videoEl.id = 'vr-active-video';
        videoEl.crossOrigin = 'anonymous';
        videoEl.setAttribute('playsinline', '');
        videoEl.setAttribute('webkit-playsinline', '');
        videoEl.src = streamUrl;
        videoEl.loop = false;

        // Add to assets
        const assets = document.getElementById('scene-assets');
        assets.appendChild(videoEl);

        // Set as video source
        screen.setAttribute('src', '#vr-active-video');

        // Position in front of camera
        const camera = document.getElementById('camera');
        const camPos = camera.getAttribute('position');
        const rigPos = document.getElementById('camera-rig').getAttribute('position');

        player.setAttribute('position', `${rigPos.x} ${rigPos.y + 1.8} ${rigPos.z - 3}`);
        player.setAttribute('visible', 'true');

        // Play with user gesture handling
        videoEl.play().catch(e => {
            console.warn('Autoplay blocked, user must interact:', e);
        });

        activeVideo = videoEl;
    }

    function closeVideoPlayer() {
        const player = document.getElementById('video-player');
        player.setAttribute('visible', 'false');

        if (activeVideo) {
            activeVideo.pause();
            activeVideo.src = '';
            activeVideo.remove();
            activeVideo = null;
        }
    }

    // ======================== UI HELPERS ========================

    function setStatus(msg) {
        const el = document.getElementById('loading-status');
        if (el) el.textContent = msg;
    }

    function showRoomHud(name) {
        const hud = document.getElementById('room-hud');
        const label = document.getElementById('room-hud-name');
        label.textContent = name;
        hud.classList.remove('hidden');
    }

    function truncate(str, max) {
        if (!str) return '';
        return str.length > max ? str.substring(0, max - 1) + '…' : str;
    }

    function formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

})();
