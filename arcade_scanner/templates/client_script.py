CLIENT_JS = """
            let currentFilter = 'all';
            let currentCodec = 'all';
            let currentSort = 'bitrate';
            let currentLayout = 'grid'; // grid or list
            let workspaceMode = 'lobby'; // lobby, mixed, vault
            let currentFolder = 'all';

            // --- STARFIELD ---
            const canvas = document.getElementById('starfield');
            const ctx = canvas.getContext('2d');
            let stars = [];
            function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
            window.onresize = resize; resize();

            for(let i=0; i<200; i++) {
                stars.push({ x: Math.random()*canvas.width, y: Math.random()*canvas.height, size: Math.random()*2, speed: Math.random()*0.5 + 0.1 });
            }

            function animate() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '#fff';
                stars.forEach(s => {
                    ctx.beginPath();
                    ctx.arc(s.x, s.y, s.size, 0, Math.PI*2);
                    ctx.fill();
                    s.y += s.speed;
                    if(s.y > canvas.height) s.y = 0;
                });
                requestAnimationFrame(animate);
            }
            animate();

            // --- UI LOGIC ---
            function setFilter(f) {
                currentFilter = f;
                document.querySelectorAll('[id^="f-"]').forEach(b => b.classList.remove('active'));
                document.getElementById('f-' + f).classList.add('active');
                if(f === 'all') {
                    currentCodec = 'all';
                    document.getElementById('codecSelect').value = 'all';
                }
                filterAndSort();
            }

            function setCodecFilter(c) {
                currentCodec = c;
                filterAndSort();
            }

            function setSort(s) {
                currentSort = s;
                filterAndSort();
            }

            function setWorkspaceMode(mode) {
                workspaceMode = mode;
                
                // Update buttons
                document.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
                document.getElementById('m-' + mode).classList.add('active');
                
                // Update theme
                if (mode === 'vault') {
                    document.body.classList.add('vault-mode');
                } else {
                    document.body.classList.remove('vault-mode');
                }
                
                filterAndSort();
            }

            function toggleHidden(card) {
                const isHidden = card.getAttribute('data-hidden') === 'true';
                const newState = !isHidden;
                const path = card.getAttribute('data-path');
                
                card.setAttribute('data-hidden', newState);
                fetch(`http://localhost:${window.SERVER_PORT}/hide?path=` + encodeURIComponent(path) + `&state=${newState}`);
                
                const btn = card.querySelector('.hide-toggle-btn .material-icons');
                btn.innerText = newState ? 'visibility' : 'visibility_off';
                
                // If the new state contradicts the current workspace mode, hide it with a fade
                const shouldHide = (workspaceMode === 'lobby' && newState) || (workspaceMode === 'vault' && !newState);
                
                if (shouldHide) {
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.8)';
                    setTimeout(() => filterAndSort(), 300);
                }
            }

            function toggleLayout() {
                currentLayout = currentLayout === 'grid' ? 'list' : 'grid';
                const grid = document.getElementById('videoGrid');
                const btn = document.getElementById('toggleView');
                
                if(currentLayout === 'list') {
                    grid.classList.add('list-view');
                    btn.innerHTML = '<span class="material-icons">view_module</span>';
                } else {
                    grid.classList.remove('list-view');
                    btn.innerHTML = '<span class="material-icons">view_list</span>';
                }
            }

            // --- PREVIEW LOGIC (with Intent Delay) ---
            function handleMouseEnter(container) {
                const video = container.querySelector('video');
                container.hoverTimeout = setTimeout(() => {
                    const src = video.getAttribute('data-src');
                    if (src && !video.getAttribute('src')) {
                        video.src = src;
                        video.load(); 
                        video.play().catch(e => {
                            console.log("Preview play blocked, retrying once", e);
                            video.src = src;
                            video.play();
                        });
                    }
                }, 450); // Intent delay
            }

            function handleMouseLeave(container) {
                const video = container.querySelector('video');
                clearTimeout(container.hoverTimeout);
                video.pause();
                video.removeAttribute('src');
                video.load();
            }

            // --- LAZY RENDERING (Intersection Observer) ---
            const observerOptions = { root: null, rootMargin: '200px', threshold: 0.1 };
            const revealObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const card = entry.target;
                        card.style.opacity = "1";
                        card.style.transform = "translateY(0)";
                        observer.unobserve(card);
                    }
                });
            }, observerOptions);

            function initLazyLoading() {
                document.querySelectorAll('.video-card-container').forEach(card => {
                    card.style.opacity = "0";
                    card.style.transform = "translateY(20px)";
                    card.style.transition = "0.5s cubic-bezier(0.2, 1, 0.2, 1)";
                    revealObserver.observe(card);
                });
            }

            // --- CINEMA MODE ---
            function openCinema(container) {
                const card = container.closest('.video-card-container');
                const path = card.getAttribute('data-path');
                const name = card.querySelector('.file-name').innerText;
                const modal = document.getElementById('cinemaModal');
                const video = document.getElementById('cinemaVideo');
                const title = document.getElementById('cinemaTitle');

                title.innerText = name;
                video.src = `http://localhost:${window.SERVER_PORT}/stream?path=` + encodeURIComponent(path);
                modal.classList.add('active');
                video.load();
                video.play().catch(e => {
                    console.log("Playback failed, trying muted", e);
                    video.muted = true;
                    video.play();
                });
            }

            function closeCinema() {
                const modal = document.getElementById('cinemaModal');
                const video = document.getElementById('cinemaVideo');
                modal.classList.remove('active');
                video.pause();
                video.src = '';
            }

            // Closes on Escape key or clicking outside the video
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') closeCinema();
            });

            document.getElementById('cinemaModal').addEventListener('click', (e) => {
                if (e.target.id === 'cinemaModal') closeCinema();
            });

            // --- BATCH ACTIONS ---
            function updateBatchSelection() {
                const selected = document.querySelectorAll('.video-card-container input:checked');
                const bar = document.getElementById('batchBar');
                const count = document.getElementById('batchCount');
                
                count.innerText = selected.length;
                if(selected.length > 0) {
                    bar.classList.add('active');
                } else {
                    bar.classList.remove('active');
                }
            }

            function clearSelection() {
                document.querySelectorAll('.video-card-container input:checked').forEach(i => i.checked = false);
                updateBatchSelection();
            }

            function triggerBatchHide(state) {
                const selected = document.querySelectorAll('.video-card-container input:checked');
                const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));
                
                fetch(`http://localhost:${window.SERVER_PORT}/batch_hide?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);
                
                selected.forEach(i => {
                    const card = i.closest('.video-card-container');
                    card.setAttribute('data-hidden', state);
                    const contradictions = (workspaceMode === 'lobby' && state) || (workspaceMode === 'vault' && !state);
                    if (contradictions) {
                        card.style.opacity = '0';
                    }
                });
                
                setTimeout(() => {
                    clearSelection();
                    filterAndSort();
                }, 300);
            }

            function triggerBatchCompress() {
                const selected = document.querySelectorAll('.video-card-container input:checked');
                const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));
                
                if(confirm(`Möchtest du ${paths.length} Videos nacheinander optimieren? Dies kann eine Weile dauern.`)) {
                    fetch(`http://localhost:${window.SERVER_PORT}/batch_compress?paths=` + encodeURIComponent(paths.join(',')));
                    alert("Batch Optimierung wurde im Terminal gestartet!");
                    clearSelection();
                }
            }

            // --- FOLDER EXPLORER LOGIC ---
            function toggleFolderSidebar() {
                const sidebar = document.getElementById('folderSidebar');
                sidebar.classList.toggle('active');
                if (sidebar.classList.contains('active')) {
                    renderFolderSidebar();
                }
            }

            function setFolderFilter(folder) {
                currentFolder = folder;
                filterAndSort();
                renderFolderSidebar();
            }

            function formatSize(mb) {
                if (mb > 1024) return (mb/1024).toFixed(1) + " GB";
                return mb.toFixed(0) + " MB";
            }

            function renderFolderSidebar() {
                const list = document.getElementById('folderList');
                list.innerHTML = '';
                
                const folders = Object.keys(window.FOLDERS_DATA).sort((a, b) => {
                    return window.FOLDERS_DATA[b].size_mb - window.FOLDERS_DATA[a].size_mb;
                });
                
                const maxSize = Math.max(...Object.values(window.FOLDERS_DATA).map(f => f.size_mb));

                // Add "All Folders" item
                const allItem = document.createElement('div');
                allItem.className = `folder-item ${currentFolder === 'all' ? 'active' : ''}`;
                allItem.onclick = () => setFolderFilter('all');
                allItem.innerHTML = `<div class="folder-name">ALLE ORDNER</div><div class="folder-meta"><span>Gesamte Bibliothek</span></div>`;
                list.appendChild(allItem);

                folders.forEach(path => {
                    const data = window.FOLDERS_DATA[path];
                    const item = document.createElement('div');
                    item.className = `folder-item ${currentFolder === path ? 'active' : ''}`;
                    item.onclick = () => setFolderFilter(path);
                    
                    const relWidth = (data.size_mb / maxSize) * 100;
                    const folderName = path.split('/').pop() || path;
                    
                    item.innerHTML = `
                        <div class="folder-name" title="${path}">${folderName}</div>
                        <div class="folder-meta">
                            <span>${data.count} Videos</span>
                            <span>${formatSize(data.size_mb)}</span>
                        </div>
                        <div class="folder-progress"><div class="folder-progress-fill" style="width: ${relWidth}%"></div></div>
                    `;
                    list.appendChild(item);
                });
            }

            function filterAndSort() {
                const search = document.getElementById('searchBar').value.toLowerCase();
                const grid = document.getElementById('videoGrid');
                const cards = Array.from(grid.querySelectorAll('.video-card-container'));
                let vCount = 0; let tSize = 0;

                // Dynamic Sorting Engine
                cards.sort((a, b) => {
                    if (currentSort === 'bitrate') {
                        return parseFloat(b.getAttribute('data-bitrate')) - parseFloat(a.getAttribute('data-bitrate'));
                    } else if (currentSort === 'size') {
                        return parseFloat(b.getAttribute('data-size')) - parseFloat(a.getAttribute('data-size'));
                    } else if (currentSort === 'name') {
                        const nameA = a.querySelector('.file-name').innerText.toLowerCase();
                        const nameB = b.querySelector('.file-name').innerText.toLowerCase();
                        return nameA.localeCompare(nameB);
                    }
                    return 0;
                });

                cards.forEach(card => {
                    const text = card.innerText.toLowerCase();
                    const status = card.getAttribute('data-status');
                    const codec = card.getAttribute('data-codec');
                    
                    const matchesFilter = (currentFilter === 'all' || status === currentFilter);
                    const matchesCodec = (currentCodec === 'all' || codec === currentCodec);
                    const matchesSearch = text.includes(search);
                    const isHidden = card.getAttribute('data-hidden') === 'true';
                    const videoFolder = card.getAttribute('data-folder');
                    
                    const matchesFolder = (currentFolder === 'all' || videoFolder === currentFolder);
                    
                    let matchesWorkspace = true;
                    if (workspaceMode === 'lobby') matchesWorkspace = !isHidden;
                    else if (workspaceMode === 'vault') matchesWorkspace = isHidden;
                    
                    const matches = matchesFilter && matchesCodec && matchesSearch && matchesWorkspace && matchesFolder;
                    
                    card.style.display = matches ? '' : 'none';
                    if(matches) { vCount++; tSize += parseFloat(card.getAttribute('data-size')); }
                    // Re-append to maintain sorted order in the DOM
                    grid.appendChild(card);
                });

                document.getElementById('count-total').innerText = vCount;
                if (tSize > 1024 * 1024) {
                    document.getElementById('size-total').innerText = (tSize / (1024 * 1024)).toFixed(2) + " TB";
                } else if (tSize > 1024) {
                    document.getElementById('size-total').innerText = (tSize / 1024).toFixed(2) + " GB";
                } else {
                    document.getElementById('size-total').innerText = tSize.toFixed(0) + " MB";
                }
                
                initLazyLoading();
            }
            window.onload = () => {
                filterAndSort();
                renderFolderSidebar();
            };
"""
