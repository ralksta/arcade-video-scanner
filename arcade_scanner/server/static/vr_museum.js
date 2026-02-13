/**
 * VR Museum — Arcade Gallery
 * Immersive WebXR gallery for Meta Quest 3
 * 
 * Architecture:
 *  - Fetches /api/vr/gallery for room/video data
 *  - Procedurally builds gallery rooms per collection
 *  - Rooms connected via portals (teleport on click)
 *  - Videos displayed as framed art on walls
 *  - Click thumbnail → floating video player
 */

(function () {
    'use strict';

    // ======================== CONSTANTS ========================
    const ROOM_WIDTH = 16;
    const ROOM_DEPTH = 16;
    const ROOM_HEIGHT = 5;
    const FRAMES_PER_WALL = 4;
    const FRAME_WIDTH = 2.4;
    const FRAME_HEIGHT = 1.5;
    const FRAME_BORDER = 0.12;
    const FRAME_Y = 2.1;

    // Colors — dark luxury gallery
    const C = {
        // Walls & structure
        wallDark: '#0c0606',
        wallPanel: '#110909',
        wallMolding: '#1a0e0e',
        floor: '#0a0606',
        floorAccent: '#140c0c',
        ceiling: '#070404',
        // Frames
        frameBronze: '#b87333',
        frameGold: '#c9a055',
        frameMatte: '#0f0808',
        // Accents
        portalFrame: '#8b4513',
        portalGlow: '#ff2255',
        textGold: '#d4a574',
        textDim: '#8a6050',
        // Lighting
        spotWarm: '#ffcc88',
        spotPink: '#ff4477',
        spotAmber: '#ff8844',
        ambient: '#180a0a',
        // Trim
        leather: '#1e0d0d',
        velvet: '#2a0a14',
        brass: '#cd9b3a',
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

        // Add atmospheric fog
        const scene = document.getElementById('vr-scene');
        scene.setAttribute('fog', 'type: exponential; color: #0a0505; density: 0.015');

        // Build lobby
        buildLobby(root, rooms);

        // Build each collection room
        rooms.forEach((room, i) => {
            const pos = getRoomPosition(i + 1);
            buildRoom(root, room, i, pos);
        });

        // Camera start
        document.getElementById('camera-rig').setAttribute('position', '0 0 2');

        // Hide loading
        setTimeout(() => {
            document.getElementById('loading-overlay').classList.add('hidden');
            showRoomHud('Lobby');
        }, 800);

        // Video player close
        document.getElementById('player-close').addEventListener('click', closeVideoPlayer);
    }

    function getRoomPosition(index) {
        return { x: 0, y: 0, z: -(index * (ROOM_DEPTH + 6)) };
    }

    // ======================== LOBBY ========================
    function buildLobby(parent, rooms) {
        const el = document.createElement('a-entity');
        el.setAttribute('id', 'room-lobby');

        const portalCount = rooms.length;
        const W = Math.max(ROOM_WIDTH, portalCount * 4.5);
        const D = ROOM_DEPTH;
        const H = ROOM_HEIGHT + 1; // Grand height for lobby

        // ---- Architectural shell ----
        buildFloor(el, W, D);
        buildCeiling(el, W, D, H);
        buildDecoratedWall(el, W, H, { z: D / 2, rotY: 0 });       // Back wall
        buildDecoratedWall(el, D, H, { x: -W / 2, rotY: 90 });     // Left
        buildDecoratedWall(el, D, H, { x: W / 2, rotY: -90 });     // Right

        // ---- Grand title ----
        const title = document.createElement('a-text');
        title.setAttribute('value', 'ARCADE GALLERY');
        title.setAttribute('position', `0 ${H - 1} ${D / 2 - 0.3}`);
        title.setAttribute('rotation', '0 180 0');
        title.setAttribute('align', 'center');
        title.setAttribute('color', C.frameGold);
        title.setAttribute('font', 'mozillavr');
        title.setAttribute('scale', '8 8 8');
        title.setAttribute('opacity', '0.9');
        el.appendChild(title);

        // Subtitle
        const sub = document.createElement('a-text');
        sub.setAttribute('value', `${rooms.length} COLLECTIONS`);
        sub.setAttribute('position', `0 ${H - 1.8} ${D / 2 - 0.3}`);
        sub.setAttribute('rotation', '0 180 0');
        sub.setAttribute('align', 'center');
        sub.setAttribute('color', C.textDim);
        sub.setAttribute('font', 'mozillavr');
        sub.setAttribute('scale', '3 3 3');
        el.appendChild(sub);

        // ---- Lighting ----
        // Central chandelier-style light
        addLight(el, 'point', C.spotWarm, 1.0, W * 1.2, `0 ${H - 0.5} 0`);
        // Pink accent from sides
        addLight(el, 'point', C.spotPink, 0.2, 10, `${W / 3} ${H - 1} ${-D / 4}`);
        addLight(el, 'point', C.spotPink, 0.2, 10, `${-W / 3} ${H - 1} ${-D / 4}`);

        // ---- Floor runner (velvet carpet strip) ----
        const runner = document.createElement('a-plane');
        runner.setAttribute('width', '2.5');
        runner.setAttribute('height', String(D));
        runner.setAttribute('position', '0 0.02 0');
        runner.setAttribute('rotation', '-90 0 0');
        runner.setAttribute('material', `color: ${C.velvet}; roughness: 0.6; metalness: 0.05; side: double`);
        el.appendChild(runner);

        // ---- Portals ----
        const spacing = W / (portalCount + 1);
        rooms.forEach((room, i) => {
            const px = -W / 2 + spacing * (i + 1);
            buildPortal(el, room.name, room.video_count || 0, i, px, -D / 2, '0 0 0');
        });

        parent.appendChild(el);
    }

    // ======================== GALLERY ROOM ========================
    function buildRoom(parent, roomData, idx, offset) {
        const el = document.createElement('a-entity');
        el.setAttribute('id', `room-${idx}`);
        el.setAttribute('position', `${offset.x} ${offset.y} ${offset.z}`);

        const W = ROOM_WIDTH;
        const D = ROOM_DEPTH;
        const H = ROOM_HEIGHT;

        // ---- Shell ----
        buildFloor(el, W, D);
        buildCeiling(el, W, D, H);

        // ---- Room title on back wall ----
        buildDecoratedWall(el, W, H, { z: D / 2, rotY: 0 });
        const title = document.createElement('a-text');
        title.setAttribute('value', roomData.name.toUpperCase());
        title.setAttribute('position', `0 ${H - 0.7} ${D / 2 - 0.2}`);
        title.setAttribute('rotation', '0 180 0');
        title.setAttribute('align', 'center');
        title.setAttribute('color', C.frameGold);
        title.setAttribute('font', 'mozillavr');
        title.setAttribute('scale', '5 5 5');
        el.appendChild(title);

        // Video count badge
        const badge = document.createElement('a-text');
        badge.setAttribute('value', `${roomData.video_count || 0} VIDEOS`);
        badge.setAttribute('position', `0 ${H - 1.3} ${D / 2 - 0.2}`);
        badge.setAttribute('rotation', '0 180 0');
        badge.setAttribute('align', 'center');
        badge.setAttribute('color', C.textDim);
        badge.setAttribute('font', 'mozillavr');
        badge.setAttribute('scale', '2.5 2.5 2.5');
        el.appendChild(badge);

        // Left wall
        buildDecoratedWall(el, D, H, { x: -W / 2, rotY: 90 });
        // Right wall
        buildDecoratedWall(el, D, H, { x: W / 2, rotY: -90 });

        // Front wall with doorway
        buildFrontWallWithDoor(el, W, H, D);

        // ---- Distribute videos across walls ----
        const videos = roomData.videos || [];
        const walls = distributeToWalls(videos);

        placeFramesOnWall(el, walls.back, {
            center: [0, FRAME_Y, D / 2 - 0.15],
            facing: [0, 180, 0],
            max: FRAMES_PER_WALL
        }, idx);

        placeFramesOnWall(el, walls.left, {
            center: [-W / 2 + 0.15, FRAME_Y, 0],
            facing: [0, 90, 0],
            max: FRAMES_PER_WALL,
            axis: 'z'
        }, idx);

        placeFramesOnWall(el, walls.right, {
            center: [W / 2 - 0.15, FRAME_Y, 0],
            facing: [0, -90, 0],
            max: FRAMES_PER_WALL,
            axis: 'z'
        }, idx);

        placeFramesOnWall(el, walls.front, {
            center: [0, FRAME_Y, -D / 2 + 0.15],
            facing: [0, 0, 0],
            max: 2
        }, idx);

        // ---- Room lighting ----
        addLight(el, 'point', C.spotWarm, 0.7, 20, `0 ${H - 0.3} 0`);
        addLight(el, 'point', C.spotPink, 0.12, 10, `${W / 3} ${H - 1} ${D / 4}`);
        addLight(el, 'point', C.spotAmber, 0.1, 8, `${-W / 3} 1.5 ${-D / 4}`);

        // ---- Return portal ----
        buildPortal(el, '← LOBBY', null, -1, 0, -D / 2, '0 180 0', true);

        parent.appendChild(el);
    }

    // ======================== ARCHITECTURAL ELEMENTS ========================

    /**
     * Polished floor with center accent strip and subtle reflection look.
     */
    function buildFloor(parent, w, d) {
        // Main floor
        const floor = document.createElement('a-plane');
        floor.setAttribute('width', w);
        floor.setAttribute('height', d);
        floor.setAttribute('position', '0 0.005 0');
        floor.setAttribute('rotation', '-90 0 0');
        floor.setAttribute('material', `color: ${C.floor}; roughness: 0.25; metalness: 0.4; side: double`);
        parent.appendChild(floor);

        // Perimeter border (brass inlay effect)
        const borderW = 0.08;
        const positions = [
            { w: w, h: borderW, x: 0, z: d / 2 - borderW / 2 },     // front
            { w: w, h: borderW, x: 0, z: -(d / 2 - borderW / 2) },  // back
            { w: borderW, h: d, x: w / 2 - borderW / 2, z: 0 },     // right
            { w: borderW, h: d, x: -(w / 2 - borderW / 2), z: 0 },  // left
        ];
        positions.forEach(p => {
            const strip = document.createElement('a-plane');
            strip.setAttribute('width', p.w);
            strip.setAttribute('height', p.h);
            strip.setAttribute('position', `${p.x} 0.01 ${p.z}`);
            strip.setAttribute('rotation', '-90 0 0');
            strip.setAttribute('material', `color: ${C.brass}; roughness: 0.2; metalness: 0.8; side: double; opacity: 0.3`);
            parent.appendChild(strip);
        });
    }

    /**
     * Ceiling with subtle recessed panel look.
     */
    function buildCeiling(parent, w, d, h) {
        const ceil = document.createElement('a-plane');
        ceil.setAttribute('width', w);
        ceil.setAttribute('height', d);
        ceil.setAttribute('position', `0 ${h} 0`);
        ceil.setAttribute('rotation', '90 0 0');
        ceil.setAttribute('material', `color: ${C.ceiling}; roughness: 0.9; metalness: 0.0; side: double`);
        parent.appendChild(ceil);

        // Coffered ceiling accent (darker inset)
        const inset = document.createElement('a-plane');
        inset.setAttribute('width', w - 2);
        inset.setAttribute('height', d - 2);
        inset.setAttribute('position', `0 ${h - 0.01} 0`);
        inset.setAttribute('rotation', '90 0 0');
        inset.setAttribute('material', `color: #050202; roughness: 0.95; side: double`);
        parent.appendChild(inset);
    }

    /**
     * Decorated wall: base panel + wainscoting + crown molding + baseboard.
     */
    function buildDecoratedWall(parent, wallW, wallH, opts) {
        const x = opts.x || 0;
        const z = opts.z || 0;
        const rotY = opts.rotY || 0;

        const wallGroup = document.createElement('a-entity');
        wallGroup.setAttribute('position', `${x} 0 ${z}`);
        wallGroup.setAttribute('rotation', `0 ${rotY} 0`);

        // Main wall surface
        const wall = document.createElement('a-plane');
        wall.setAttribute('width', wallW);
        wall.setAttribute('height', wallH);
        wall.setAttribute('position', `0 ${wallH / 2} 0`);
        wall.setAttribute('material', `color: ${C.wallDark}; roughness: 0.85; metalness: 0.03; side: double`);
        wallGroup.appendChild(wall);

        // Wainscoting panel (lower 1/3 of wall, slightly lighter)
        const wainscotH = wallH * 0.3;
        const wainscot = document.createElement('a-plane');
        wainscot.setAttribute('width', wallW - 0.1);
        wainscot.setAttribute('height', wainscotH);
        wainscot.setAttribute('position', `0 ${wainscotH / 2 + 0.15} 0.01`);
        wainscot.setAttribute('material', `color: ${C.wallPanel}; roughness: 0.5; metalness: 0.08; side: double`);
        wallGroup.appendChild(wainscot);

        // Chair rail (divider between wainscoting and upper wall)
        const rail = document.createElement('a-plane');
        rail.setAttribute('width', wallW);
        rail.setAttribute('height', 0.06);
        rail.setAttribute('position', `0 ${wainscotH + 0.15} 0.02`);
        rail.setAttribute('material', `color: ${C.brass}; roughness: 0.3; metalness: 0.6; side: double; opacity: 0.5`);
        wallGroup.appendChild(rail);

        // Crown molding (top edge)
        const crown = document.createElement('a-plane');
        crown.setAttribute('width', wallW);
        crown.setAttribute('height', 0.08);
        crown.setAttribute('position', `0 ${wallH - 0.05} 0.02`);
        crown.setAttribute('material', `color: ${C.brass}; roughness: 0.3; metalness: 0.6; side: double; opacity: 0.4`);
        wallGroup.appendChild(crown);

        // Baseboard
        const baseboard = document.createElement('a-plane');
        baseboard.setAttribute('width', wallW);
        baseboard.setAttribute('height', 0.12);
        baseboard.setAttribute('position', `0 0.06 0.015`);
        baseboard.setAttribute('material', `color: ${C.leather}; roughness: 0.4; metalness: 0.15; side: double`);
        wallGroup.appendChild(baseboard);

        parent.appendChild(wallGroup);
    }

    /**
     * Front wall with centered doorway.
     */
    function buildFrontWallWithDoor(parent, w, h, d) {
        const doorW = 2.2;
        const doorH = 3;
        const sideW = (w - doorW) / 2;
        const wallZ = -d / 2;

        // Left side
        const left = document.createElement('a-plane');
        left.setAttribute('width', sideW);
        left.setAttribute('height', h);
        left.setAttribute('position', `${-(doorW / 2 + sideW / 2)} ${h / 2} ${wallZ}`);
        left.setAttribute('rotation', '0 180 0');
        left.setAttribute('material', `color: ${C.wallDark}; roughness: 0.85; metalness: 0.03; side: double`);
        parent.appendChild(left);

        // Right side
        const right = document.createElement('a-plane');
        right.setAttribute('width', sideW);
        right.setAttribute('height', h);
        right.setAttribute('position', `${(doorW / 2 + sideW / 2)} ${h / 2} ${wallZ}`);
        right.setAttribute('rotation', '0 180 0');
        right.setAttribute('material', `color: ${C.wallDark}; roughness: 0.85; metalness: 0.03; side: double`);
        parent.appendChild(right);

        // Header above door
        const header = document.createElement('a-plane');
        header.setAttribute('width', doorW);
        header.setAttribute('height', h - doorH);
        header.setAttribute('position', `0 ${doorH + (h - doorH) / 2} ${wallZ}`);
        header.setAttribute('rotation', '0 180 0');
        header.setAttribute('material', `color: ${C.wallDark}; roughness: 0.85; metalness: 0.03; side: double`);
        parent.appendChild(header);

        // Door frame trim (brass)
        // Left jamb
        const jamb1 = document.createElement('a-box');
        jamb1.setAttribute('width', '0.08');
        jamb1.setAttribute('height', String(doorH));
        jamb1.setAttribute('depth', '0.08');
        jamb1.setAttribute('position', `${-doorW / 2} ${doorH / 2} ${wallZ}`);
        jamb1.setAttribute('material', `color: ${C.brass}; roughness: 0.3; metalness: 0.6; opacity: 0.6`);
        parent.appendChild(jamb1);

        // Right jamb
        const jamb2 = document.createElement('a-box');
        jamb2.setAttribute('width', '0.08');
        jamb2.setAttribute('height', String(doorH));
        jamb2.setAttribute('depth', '0.08');
        jamb2.setAttribute('position', `${doorW / 2} ${doorH / 2} ${wallZ}`);
        jamb2.setAttribute('material', `color: ${C.brass}; roughness: 0.3; metalness: 0.6; opacity: 0.6`);
        parent.appendChild(jamb2);

        // Lintel
        const lintel = document.createElement('a-box');
        lintel.setAttribute('width', String(doorW + 0.16));
        lintel.setAttribute('height', '0.08');
        lintel.setAttribute('depth', '0.08');
        lintel.setAttribute('position', `0 ${doorH + 0.04} ${wallZ}`);
        lintel.setAttribute('material', `color: ${C.brass}; roughness: 0.3; metalness: 0.6; opacity: 0.6`);
        parent.appendChild(lintel);
    }

    // ======================== VIDEO FRAMES ========================

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

    function placeFramesOnWall(parent, videos, opts, roomIdx) {
        if (!videos.length) return;
        const count = Math.min(videos.length, opts.max);
        const gap = 0.8;
        const totalW = count * FRAME_WIDTH + (count - 1) * gap;
        const start = -totalW / 2 + FRAME_WIDTH / 2;
        const axis = opts.axis || 'x';

        for (let i = 0; i < count; i++) {
            const off = start + i * (FRAME_WIDTH + gap);
            let pos;
            if (axis === 'x') {
                pos = [opts.center[0] + off, opts.center[1], opts.center[2]];
            } else {
                pos = [opts.center[0], opts.center[1], opts.center[2] + off];
            }
            buildVideoFrame(parent, videos[i], pos, opts.facing, `r${roomIdx}_f${i}`);
        }
    }

    /**
     * Build a premium framed video thumbnail with spotlight.
     */
    function buildVideoFrame(parent, video, pos, rot, id) {
        const frame = document.createElement('a-entity');
        frame.setAttribute('position', pos.join(' '));
        frame.setAttribute('rotation', rot.join(' '));

        const bw = FRAME_BORDER;
        const fw = FRAME_WIDTH + bw * 2;
        const fh = FRAME_HEIGHT + bw * 2;

        // Shadow backing (depth behind frame)
        const backing = document.createElement('a-box');
        backing.setAttribute('width', fw + 0.04);
        backing.setAttribute('height', fh + 0.04);
        backing.setAttribute('depth', '0.06');
        backing.setAttribute('position', '0 0 -0.04');
        backing.setAttribute('material', `color: #000000; roughness: 0.9`);
        frame.appendChild(backing);

        // Outer frame (bronze/gold)
        const outer = document.createElement('a-plane');
        outer.setAttribute('width', fw);
        outer.setAttribute('height', fh);
        outer.setAttribute('position', '0 0 -0.015');
        outer.setAttribute('material', `color: ${C.frameBronze}; roughness: 0.25; metalness: 0.75; side: double`);
        frame.appendChild(outer);

        // Inner matte (dark leather feel)
        const matte = document.createElement('a-plane');
        matte.setAttribute('width', FRAME_WIDTH + 0.04);
        matte.setAttribute('height', FRAME_HEIGHT + 0.04);
        matte.setAttribute('position', '0 0 -0.008');
        matte.setAttribute('material', `color: ${C.frameMatte}; roughness: 0.5; metalness: 0.05; side: double`);
        frame.appendChild(matte);

        // Thumbnail image (clickable)
        const thumb = document.createElement('a-plane');
        thumb.setAttribute('width', FRAME_WIDTH);
        thumb.setAttribute('height', FRAME_HEIGHT);
        thumb.setAttribute('class', 'clickable');
        thumb.setAttribute('id', `frame-${id}`);

        if (video.thumbnail) {
            thumb.setAttribute('material', `src: url(${video.thumbnail}); shader: flat; side: double`);
        } else {
            thumb.setAttribute('material', `color: ${C.wallPanel}; shader: flat; side: double`);
        }

        thumb.dataset.streamUrl = video.stream_url || '';
        thumb.dataset.title = video.title || '';

        thumb.addEventListener('click', function () {
            openVideoPlayer(this.dataset.streamUrl, this.dataset.title);
        });

        // Hover glow effect on outer frame
        thumb.addEventListener('mouseenter', function () {
            outer.setAttribute('material', 'emissive', C.spotPink);
            outer.setAttribute('material', 'emissiveIntensity', '0.4');
        });
        thumb.addEventListener('mouseleave', function () {
            outer.setAttribute('material', 'emissive', '#000000');
            outer.setAttribute('material', 'emissiveIntensity', '0');
        });

        frame.appendChild(thumb);

        // Title plaque below frame
        if (video.title) {
            // Plaque backing
            const plaqueW = Math.min(FRAME_WIDTH, 2.2);
            const plaque = document.createElement('a-plane');
            plaque.setAttribute('width', plaqueW);
            plaque.setAttribute('height', '0.25');
            plaque.setAttribute('position', `0 ${-(fh / 2 + 0.25)} 0.005`);
            plaque.setAttribute('material', `color: ${C.leather}; roughness: 0.4; metalness: 0.1; side: double`);
            frame.appendChild(plaque);

            // Title text
            const label = document.createElement('a-text');
            label.setAttribute('value', truncate(video.title, 24));
            label.setAttribute('position', `0 ${-(fh / 2 + 0.25)} 0.015`);
            label.setAttribute('align', 'center');
            label.setAttribute('color', C.textGold);
            label.setAttribute('scale', '1.3 1.3 1.3');
            label.setAttribute('font', 'mozillavr');
            label.setAttribute('wrapCount', '30');
            label.setAttribute('width', String(plaqueW - 0.2));
            frame.appendChild(label);
        }

        // Duration badge (top-right corner)
        if (video.duration && video.duration > 0) {
            const durText = formatDuration(video.duration);
            const dur = document.createElement('a-text');
            dur.setAttribute('value', durText);
            dur.setAttribute('position', `${FRAME_WIDTH / 2 - 0.1} ${FRAME_HEIGHT / 2 - 0.1} 0.01`);
            dur.setAttribute('align', 'right');
            dur.setAttribute('color', '#ffffff');
            dur.setAttribute('scale', '1.0 1.0 1.0');
            dur.setAttribute('font', 'mozillavr');

            // Duration background
            const durBg = document.createElement('a-plane');
            durBg.setAttribute('width', '0.6');
            durBg.setAttribute('height', '0.18');
            durBg.setAttribute('position', `${FRAME_WIDTH / 2 - 0.35} ${FRAME_HEIGHT / 2 - 0.1} 0.005`);
            durBg.setAttribute('material', 'color: #000000; opacity: 0.7; shader: flat; side: double');
            frame.appendChild(durBg);
            frame.appendChild(dur);
        }

        // Picture light (warm spot from above)
        const spot = document.createElement('a-light');
        spot.setAttribute('type', 'spot');
        spot.setAttribute('color', C.spotWarm);
        spot.setAttribute('intensity', '0.6');
        spot.setAttribute('angle', '30');
        spot.setAttribute('penumbra', '0.8');
        spot.setAttribute('distance', '5');
        spot.setAttribute('position', '0 1.8 1.2');
        spot.setAttribute('target', `#frame-${id}`);
        frame.appendChild(spot);

        parent.appendChild(frame);
    }

    // ======================== PORTALS ========================

    function buildPortal(parent, label, videoCount, targetIndex, x, z, rot, isReturn) {
        const portal = document.createElement('a-entity');
        portal.setAttribute('position', `${x} 0 ${z}`);
        portal.setAttribute('rotation', rot);

        const pw = 1.4;     // Portal width
        const ph = 2.8;     // Portal height
        const hw = pw / 2;

        // Door frame — elegant brass
        const pieces = [
            { w: 0.1, h: ph, d: 0.1, x: -hw, y: ph / 2, z: 0 },      // left
            { w: 0.1, h: ph, d: 0.1, x: hw, y: ph / 2, z: 0 },       // right
            { w: pw + 0.2, h: 0.1, d: 0.1, x: 0, y: ph + 0.05, z: 0 }, // top
        ];
        pieces.forEach(p => {
            const box = document.createElement('a-box');
            box.setAttribute('width', p.w);
            box.setAttribute('height', p.h);
            box.setAttribute('depth', p.d);
            box.setAttribute('position', `${p.x} ${p.y} ${p.z}`);
            box.setAttribute('material', `color: ${C.brass}; roughness: 0.25; metalness: 0.7`);
            portal.appendChild(box);
        });

        // Decorative keystone at top center
        const keystone = document.createElement('a-box');
        keystone.setAttribute('width', '0.2');
        keystone.setAttribute('height', '0.2');
        keystone.setAttribute('depth', '0.12');
        keystone.setAttribute('position', `0 ${ph + 0.15} 0`);
        keystone.setAttribute('rotation', '0 0 45');
        keystone.setAttribute('material', `color: ${C.frameGold}; roughness: 0.2; metalness: 0.8`);
        portal.appendChild(keystone);

        // Portal glow plane (clickable)
        const glow = document.createElement('a-plane');
        glow.setAttribute('width', String(pw - 0.05));
        glow.setAttribute('height', String(ph - 0.05));
        glow.setAttribute('position', `0 ${ph / 2} 0`);
        glow.setAttribute('class', 'clickable');
        glow.setAttribute('material', `color: ${C.portalGlow}; opacity: 0.08; shader: flat; side: double`);
        glow.dataset.targetRoom = String(targetIndex);
        glow.addEventListener('click', function () {
            teleportToRoom(parseInt(this.dataset.targetRoom));
        });
        glow.addEventListener('mouseenter', function () {
            this.setAttribute('material', 'opacity', '0.25');
            this.setAttribute('material', 'color', '#ff4488');
        });
        glow.addEventListener('mouseleave', function () {
            this.setAttribute('material', 'opacity', '0.08');
            this.setAttribute('material', 'color', C.portalGlow);
        });
        portal.appendChild(glow);

        // Portal label
        const text = document.createElement('a-text');
        text.setAttribute('value', truncate(label, 18));
        text.setAttribute('position', `0 ${ph + 0.55} 0`);
        text.setAttribute('align', 'center');
        text.setAttribute('color', isReturn ? '#ff6699' : C.textGold);
        text.setAttribute('font', 'mozillavr');
        text.setAttribute('scale', '1.6 1.6 1.6');
        text.setAttribute('side', 'double');
        text.setAttribute('wrapCount', '20');
        text.setAttribute('width', '3');
        portal.appendChild(text);

        // Video count sub-label
        if (videoCount !== null && !isReturn) {
            const sub = document.createElement('a-text');
            sub.setAttribute('value', `${videoCount} videos`);
            sub.setAttribute('position', `0 ${ph / 2 - 0.2} 0.01`);
            sub.setAttribute('align', 'center');
            sub.setAttribute('color', C.textDim);
            sub.setAttribute('font', 'mozillavr');
            sub.setAttribute('scale', '1.2 1.2 1.2');
            sub.setAttribute('side', 'double');
            portal.appendChild(sub);
        }

        // Portal edge glow
        addLight(portal, 'point', C.portalGlow, 0.3, 4, `0 ${ph / 2} 0.3`);

        parent.appendChild(portal);
    }

    // ======================== TELEPORTATION ========================

    function teleportToRoom(roomIndex) {
        const rig = document.getElementById('camera-rig');

        if (roomIndex === -1) {
            rig.setAttribute('position', '0 0 2');
            currentRoomIndex = -1;
            showRoomHud('Lobby');
        } else {
            const pos = getRoomPosition(roomIndex + 1);
            rig.setAttribute('position', `${pos.x} ${pos.y} ${pos.z + ROOM_DEPTH / 2 - 2}`);
            currentRoomIndex = roomIndex;
            showRoomHud(galleryData.rooms[roomIndex].name);
        }
    }

    // ======================== VIDEO PLAYER ========================

    function openVideoPlayer(streamUrl, title) {
        if (!streamUrl) return;

        const player = document.getElementById('video-player');
        const screen = document.getElementById('player-screen');

        // Remove old video element
        const old = document.getElementById('vr-active-video');
        if (old) old.remove();

        const videoEl = document.createElement('video');
        videoEl.id = 'vr-active-video';
        videoEl.crossOrigin = 'anonymous';
        videoEl.setAttribute('playsinline', '');
        videoEl.setAttribute('webkit-playsinline', '');
        videoEl.src = streamUrl;
        videoEl.loop = false;

        document.getElementById('scene-assets').appendChild(videoEl);
        screen.setAttribute('src', '#vr-active-video');

        // Position in front of user
        const rigPos = document.getElementById('camera-rig').getAttribute('position');
        player.setAttribute('position', `${rigPos.x} ${rigPos.y + 1.8} ${rigPos.z - 3}`);
        player.setAttribute('visible', 'true');

        videoEl.play().catch(e => {
            console.warn('Autoplay blocked:', e);
        });
        activeVideo = videoEl;
    }

    function closeVideoPlayer() {
        document.getElementById('video-player').setAttribute('visible', 'false');
        if (activeVideo) {
            activeVideo.pause();
            activeVideo.src = '';
            activeVideo.remove();
            activeVideo = null;
        }
    }

    // ======================== HELPERS ========================

    function addLight(parent, type, color, intensity, distance, pos) {
        const l = document.createElement('a-light');
        l.setAttribute('type', type);
        l.setAttribute('color', color);
        l.setAttribute('intensity', String(intensity));
        l.setAttribute('distance', String(distance));
        l.setAttribute('position', pos);
        parent.appendChild(l);
        return l;
    }

    function setStatus(msg) {
        const el = document.getElementById('loading-status');
        if (el) el.textContent = msg;
    }

    function showRoomHud(name) {
        const hud = document.getElementById('room-hud');
        document.getElementById('room-hud-name').textContent = name;
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
