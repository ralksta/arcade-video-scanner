# -*- coding: utf-8 -*-
# Modular HTML Components using Tailwind CSS

OPTIMIZE_PANEL_COMPONENT = """
<!-- Optimize Panel (Tailwind) -->
<div id="optimizePanel" class="fixed bottom-4 left-0 right-0 mx-auto w-[96%] max-w-5xl bg-[#101018]/85 backdrop-blur-2xl border border-white/20 p-4 rounded-2xl translate-y-[150%] transition-transform duration-500 z-[10050] animate-glow-pulse glow-cyan flex flex-col gap-3">
    <!-- Active state class 'translate-y-0' handled by JS and inline CSS in HEAD -->
    
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-white/10 pb-2">
        <h3 class="text-white font-bold text-base flex items-center gap-2">
            <span class="material-icons text-arcade-cyan text-[18px]">tune</span>
            Video Optimization
        </h3>
        <button class="w-7 h-7 rounded-full flex items-center justify-center bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all group" onclick="closeOptimize()" title="Close">
            <span class="material-icons text-[16px] group-hover:rotate-90 transition-transform">close</span>
        </button>
    </div>

    <!-- Grid Layout for Settings (Compact 4-col) -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        
        <!-- Codec Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Codec Target</div>
                <span class="material-icons text-[14px] text-gray-500">memory</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full">
                <div class="flex-1 py-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="optCodecHevc" data-codec-btn="hevc" onclick="setOptCodec('hevc')">HEVC</div>
                <div class="flex-1 py-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="optCodecAv1" data-codec-btn="av1" onclick="setOptCodec('av1')">AV1 🧪</div>
            </div>
            <!-- Hidden to save vertical space, id kept for JS safety if needed initially -->
            <span class="hidden" id="optCodecDesc"></span>
        </div>

        <!-- Video Processing Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Video Stream</div>
                <span class="material-icons text-[14px] text-gray-500">movie</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full">
                <div class="flex-1 py-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="optVideoCompress" onclick="setOptVideo('compress')">Compress</div>
                <div class="flex-1 py-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="optVideoCopy" onclick="setOptVideo('copy')">Copy</div>
            </div>
            <span class="hidden" id="optVideoDesc"></span>
        </div>

        <!-- Audio Setup Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Audio Stream</div>
                <span class="material-icons text-[14px] text-gray-500">multitrack_audio</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full">
                <div class="flex-1 py-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="optAudioEnhanced" onclick="setOptAudio('enhanced')">Enhanced</div>
                <div class="flex-1 py-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="optAudioStandard" onclick="setOptAudio('standard')">Standard</div>
            </div>
            <span class="hidden" id="optAudioDesc"></span>
        </div>

        <!-- Target Quality Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col justify-center transition-colors">
            <div class="flex items-center justify-between mb-1">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Target Quality</div>
                <span class="material-icons text-[14px] text-gray-500">high_quality</span>
            </div>
            <div class="flex items-center gap-3">
                <input type="number" class="bg-black/50 border border-white/10 text-arcade-cyan font-bold px-2 py-1 rounded-lg font-mono text-center w-[60px] text-[13px] focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30" id="optQuality" placeholder="Auto">
                <div class="flex flex-col">
                    <span class="text-[10px] text-gray-400 leading-none">Q-Factor</span>
                    <span class="text-[9px] text-gray-500 italic mt-1 leading-none" id="optQualitySuggestion"></span>
                </div>
            </div>
        </div>
    </div>

    <!-- Trim & Timeline Area + Actions in same horizontal block for extreme compactness -->
    <div class="flex flex-col md:flex-row gap-3 items-end">
        <!-- Trim block -->
        <div class="bg-white/[0.02] border border-white/5 rounded-xl p-3 flex-1 flex flex-col gap-2 relative group w-full">
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-arcade-cyan/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-1000 pointer-events-none rounded-xl"></div>
            
            <div class="flex items-center justify-between relative z-10 hidden md:flex">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                    <span class="material-icons text-[14px]">content_cut</span> Trim
                </div>
                
                <div class="flex items-center gap-1.5">
                    <input type="text" class="bg-black/40 border border-white/10 text-white px-2 py-0.5 text-xs rounded-md font-mono text-center w-[75px] focus:border-arcade-cyan focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all" id="optTrimStart" placeholder="00:00:00">
                    <button class="w-[24px] h-[24px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-arcade-cyan transition-colors" onclick="setTrimFromHead('start')" title="Set Start from playhead">
                        <span class="material-icons text-[12px]">arrow_downward</span>
                    </button>
                    <div class="text-gray-600 font-mono text-[10px] mx-1">-</div>
                    <input type="text" class="bg-black/40 border border-white/10 text-white px-2 py-0.5 text-xs rounded-md font-mono text-center w-[75px] focus:border-arcade-cyan focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all" id="optTrimEnd" placeholder="END">
                    <button class="w-[24px] h-[24px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-arcade-cyan transition-colors" onclick="setTrimFromHead('end')" title="Set End from playhead">
                        <span class="material-icons text-[12px]">arrow_downward</span>
                    </button>
                    <button class="w-[24px] h-[24px] flex items-center justify-center border border-white/10 rounded-md text-red-400/70 hover:bg-red-400/10 hover:text-red-400 hover:border-red-400/30 transition-colors ml-1" onclick="clearTrim()" title="Clear Trim">
                        <span class="material-icons text-[12px]">close</span>
                    </button>
                </div>
            </div>
            
            <!-- Timeline Scrubber -->
            <div class="relative w-full mt-0.5 z-10 min-h-[50px] md:min-h-[60px]" id="optimizeTimeline"></div>
        </div>
        
        <!-- Actions -->
        <div class="flex items-center justify-end gap-2 shrink-0">
            <button class="px-4 py-2 rounded-xl text-sm font-bold text-gray-400 bg-transparent hover:bg-white/5 hover:text-white transition-colors" onclick="closeOptimize()">
                Cancel
            </button>
            <button class="btn-glitch px-5 py-2 rounded-xl text-sm font-bold cursor-pointer text-[#000] bg-arcade-cyan hover:bg-white transition-all duration-300 shadow-[0_0_15px_rgba(0,255,208,0.3)] hover:shadow-[0_0_25px_rgba(0,255,208,0.5)] transform hover:-translate-y-0.5 flex items-center justify-center gap-1.5" onclick="triggerOptimization()">
                <span class="material-icons text-[16px]">bolt</span> START
            </button>
        </div>
    </div>
</div>
"""

GIF_EXPORT_PANEL_COMPONENT = """
<!-- GIF Export Panel (Tailwind) -->
<div id="gifExportPanel" class="fixed bottom-4 left-0 right-0 mx-auto w-[96%] max-w-5xl bg-[#101018]/85 backdrop-blur-2xl border border-white/20 p-4 rounded-2xl translate-y-[150%] transition-transform duration-500 z-[10100] animate-glow-pulse glow-purple flex flex-col gap-3">
    <!-- Active state class 'translate-y-0' handled by JS -->
    
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-white/10 pb-2">
        <h3 class="text-white font-bold text-base flex items-center gap-2">
            <span class="material-icons text-purple-400 text-[18px]">gif</span>
            Export GIF
        </h3>
        <button class="w-7 h-7 rounded-full flex items-center justify-center bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all group" onclick="closeGifExport()" title="Close">
            <span class="material-icons text-[16px] group-hover:rotate-90 transition-transform">close</span>
        </button>
    </div>

    <!-- Grid Layout (5 cols: Preset / FPS / Loop / Speed / Quality) -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
        
        <!-- Preset Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Preset</div>
                <span class="text-[9px] text-gray-500 italic leading-none" id="gifPresetDesc">1280x720</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full overflow-x-auto scroller-hide">
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPreset360p" onclick="setGifPreset('360p')">360p</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPreset480p" onclick="setGifPreset('480p')">480p</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="gifPreset720p" onclick="setGifPreset('720p')">720p</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPreset1080p" onclick="setGifPreset('1080p')">1080p</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPresetOriginal" onclick="setGifPreset('original')">Max</div>
            </div>
        </div>

        <!-- FPS Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">FPS</div>
                <span class="material-icons text-[14px] text-gray-500">speed</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full overflow-x-auto scroller-hide">
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps10" onclick="setGifFps(10)">10</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="gifFps15" onclick="setGifFps(15)">15</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps20" onclick="setGifFps(20)">20</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps25" onclick="setGifFps(25)">25</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps30" onclick="setGifFps(30)">30</div>
            </div>
        </div>

        <!-- Loop Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Loop</div>
                <span class="material-icons text-[14px] text-gray-500">loop</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full">
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="gifLoop0" onclick="setGifLoop(0)" title="Loop forever">inf</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifLoop1" onclick="setGifLoop(1)" title="Play once">1x</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifLoop3" onclick="setGifLoop(3)" title="Play 3 times">3x</div>
            </div>
        </div>

        <!-- Speed Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col gap-2 transition-colors">
            <div class="flex items-center justify-between">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Speed</div>
                <span class="material-icons text-[14px] text-gray-500">fast_forward</span>
            </div>
            <div class="flex bg-black/40 rounded-lg p-1 w-full">
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifSpeed0_5" onclick="setGifSpeed(0.5)" title="Slow motion">0.5x</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="gifSpeed1_0" onclick="setGifSpeed(1.0)" title="Normal">1x</div>
                <div class="flex-1 py-1 px-1 text-center text-[12px] cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifSpeed2_0" onclick="setGifSpeed(2.0)" title="Fast forward">2x</div>
            </div>
        </div>

        <!-- Quality Card -->
        <div class="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl border border-white/5 p-2.5 flex flex-col justify-center transition-colors">
            <div class="flex items-center justify-between mb-1">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Quality</div>
                <span class="text-[9px] text-gray-500 italic leading-none font-mono">Est: <span id="gifEstimatedSize" class="text-purple-400">~0 MB</span></span>
            </div>
            <div class="flex items-center gap-3">
                <input type="number" class="bg-black/50 border border-white/10 text-purple-400 font-bold px-2 py-1 rounded-lg font-mono text-center w-[60px] text-[13px] focus:border-purple-400/50 focus:outline-none focus:ring-1 focus:ring-purple-400/30" id="gifQuality" placeholder="80" value="80" min="50" max="100" step="10" oninput="updateGifEstimate()">
                <div class="flex flex-col">
                    <span class="text-[10px] text-gray-400 leading-none">Scale: 50-100</span>
                    <span class="text-[9px] text-gray-500 italic mt-1 leading-none">Lower = smaller file</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Trim & Timeline Area + Actions -->
    <div class="flex flex-col md:flex-row gap-3 items-end">
        <!-- Trim block -->
        <div class="bg-white/[0.02] border border-white/5 rounded-xl p-3 flex-1 flex flex-col gap-2 relative group w-full">
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-1000 pointer-events-none rounded-xl"></div>
            
            <div class="flex items-center justify-between relative z-10 hidden md:flex">
                <div class="text-[10px] text-gray-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                    <span class="material-icons text-[14px]">content_cut</span> Trim
                </div>
                
                <div class="flex items-center gap-1.5">
                    <span class="text-xs text-gray-500 mr-2">Dur: <span id="gifDuration" class="text-purple-400 font-mono">0.0s</span></span>
                    
                    <input type="text" class="bg-black/40 border border-white/10 text-white px-2 py-0.5 text-xs rounded-md font-mono text-center w-[75px] focus:border-purple-400 focus:outline-none focus:ring-1 focus:ring-purple-400/30 transition-all" id="gifTrimStart" placeholder="00:00:00" oninput="updateGifEstimate()">
                    <button class="w-[24px] h-[24px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-purple-400 transition-colors" onclick="setGifTrimFromHead('start')" title="Set Start from playhead">
                        <span class="material-icons text-[12px]">arrow_downward</span>
                    </button>
                    <div class="text-gray-600 font-mono text-[10px] mx-1">-</div>
                    <input type="text" class="bg-black/40 border border-white/10 text-white px-2 py-0.5 text-xs rounded-md font-mono text-center w-[75px] focus:border-purple-400 focus:outline-none focus:ring-1 focus:ring-purple-400/30 transition-all" id="gifTrimEnd" placeholder="END" oninput="updateGifEstimate()">
                    <button class="w-[24px] h-[24px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-purple-400 transition-colors" onclick="setGifTrimFromHead('end')" title="Set End from playhead">
                        <span class="material-icons text-[12px]">arrow_downward</span>
                    </button>
                    <button class="w-[24px] h-[24px] flex items-center justify-center border border-white/10 rounded-md text-red-400/70 hover:bg-red-400/10 hover:text-red-400 hover:border-red-400/30 transition-colors ml-1" onclick="clearGifTrim()" title="Clear Trim">
                        <span class="material-icons text-[12px]">close</span>
                    </button>
                </div>
            </div>
            
            <!-- Timeline Scrubber -->
            <div class="relative w-full mt-0.5 z-10 min-h-[50px] md:min-h-[60px]" id="gifTimeline"></div>
        </div>
        
        <!-- Actions -->
        <div class="flex items-center justify-end gap-2 shrink-0">
            <button class="px-4 py-2 rounded-xl text-sm font-bold text-gray-400 bg-transparent hover:bg-white/5 hover:text-white transition-colors" onclick="closeGifExport()">
                Cancel
            </button>
            <button class="btn-glitch px-5 py-2 rounded-xl text-sm font-bold cursor-pointer text-[#000] bg-purple-500 hover:bg-white transition-all duration-300 shadow-[0_0_15px_rgba(168,85,247,0.3)] hover:shadow-[0_0_25px_rgba(168,85,247,0.5)] transform hover:-translate-y-0.5 flex items-center justify-center gap-1.5" onclick="triggerGifExport()">
                <span class="material-icons text-[16px]">gif</span> EXPORT
            </button>
        </div>
    </div>
</div>
"""

CINEMA_MODAL_COMPONENT = """
<!-- Cinema Modal (Tailwind) -->
<div id="cinemaModal" class="fixed inset-0 z-50 bg-black opacity-0 pointer-events-none transition-opacity duration-500 flex flex-col justify-center items-center">
    <!-- Active class 'opacity-100 pointer-events-auto' toggled by JS -->
    
    <button class="absolute top-4 right-4 text-white/50 hover:text-white z-50 p-2" onclick="closeCinema()">
        <span class="material-icons text-4xl">close</span>
    </button>
    
    <h2 id="cinemaTitle" class="absolute top-6 left-0 right-0 text-center text-white/80 font-light tracking-[4px] text-lg uppercase pointer-events-none z-40 drop-shadow-lg transition-transform duration-500">Movie Player</h2>
    
    <video id="cinemaVideo" controls preload="metadata" class="max-w-full max-h-[80vh] w-auto h-auto shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-lg outline-none transition-all duration-500 origin-bottom"></video>
    
    <img id="cinemaImage" class="hidden max-w-full max-h-[80vh] w-auto h-auto shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-lg object-contain transition-all duration-500 origin-bottom" src="">
    
    <div id="cinemaSourceMessage" class="hidden flex-col items-center justify-center bg-black/60 backdrop-blur-md rounded-2xl p-8 border border-purple-500/30 shadow-[0_0_50px_rgba(168,85,247,0.15)] text-center animate-glow-pulse glow-purple max-w-md w-full mx-4 z-40">
        <span class="material-icons text-purple-400 text-6xl mb-4">movie_filter</span>
        <h3 class="text-white text-xl font-bold tracking-widest mb-2">SOURCE MEDIA</h3>
        <p class="text-gray-400 text-sm mb-6 leading-relaxed">This high-bitrate file exceeds streaming limits and is preserved in raw quality.</p>
        <div class="flex gap-4 w-full">
            <button onclick="cinemaLocate()" class="flex-1 py-3 px-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-white font-bold text-sm tracking-wide transition-all flex items-center justify-center gap-2">
                <span class="material-icons text-[18px]">folder_open</span> LOCATE
            </button>
            <a id="cinemaDownloadBtn" href="" download class="flex-1 py-3 px-4 bg-purple-500/20 hover:bg-purple-500 text-purple-300 hover:text-white border border-purple-500/50 hover:shadow-[0_0_20px_rgba(168,85,247,0.4)] rounded-xl font-bold text-sm tracking-wide transition-all flex items-center justify-center gap-2">
                <span class="material-icons text-[18px]">download</span> DOWNLOAD
            </a>
        </div>
    </div>
    
    <div id="cinemaInfoPanel" class="absolute top-20 right-4 w-80 bg-black/80 backdrop-blur-md border border-white/10 rounded-lg p-4 transform translate-x-[120%] transition-transform duration-300 z-40 text-sm text-gray-300 animate-glow-pulse glow-cyan">
        <div class="flex items-center gap-2 mb-3 text-white font-bold border-b border-white/10 pb-2">
            <span class="material-icons text-sm">info</span>
            <span>Technical Details</span>
        </div>
        <div id="cinemaInfoContent" class="space-y-2 text-xs font-mono"></div>
    </div>
    
    <!-- Assigned Tags Display (Visible List with Remove X) -->
    <div id="cinemaAssignedTags" class="absolute top-20 left-4 max-w-sm flex flex-wrap gap-2 z-40 pointer-events-auto">
        <!-- Populated by JS -->
    </div>
    
    <!-- Tag Picker Dropdown (appears above the Tags button) -->
    <div id="cinemaTagPanel" class="hidden absolute bottom-24 left-1/2 -translate-x-1/2 bg-black/90 backdrop-blur-md border border-white/10 rounded-xl p-3 z-50 min-w-[200px] max-w-[320px] animate-glow-pulse glow-cyan">
        <div class="flex items-center gap-2 mb-2 text-white/80 text-xs border-b border-white/10 pb-2">
            <span class="material-icons text-sm text-arcade-cyan">label</span>
            <span class="font-semibold uppercase tracking-wide">Assign Tags</span>
        </div>
        <div id="cinemaTagPicker" class="flex flex-wrap gap-1.5">
            <!-- Populated by JS -->
        </div>
    </div>
    
    <div id="cinemaActions" class="cinema-actions absolute bottom-8 flex gap-3 z-40">

        <!-- Info Button -->
        <button class="flex flex-col items-center gap-1.5 transition-all group" onclick="toggleCinemaInfo()" title="Technical Details [I]">
            <div class="w-12 h-12 rounded-xl bg-white/8 backdrop-blur-sm flex items-center justify-center border border-white/15 group-hover:bg-white/18 group-hover:border-white/35 group-hover:scale-110 transition-all shadow-lg">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="text-gray-300 group-hover:text-white transition-colors">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-gray-500 group-hover:text-white transition-colors">Info</span>
        </button>

        <!-- Locate Button -->
        <button id="cinemaLocateBtn" class="flex flex-col items-center gap-1.5 transition-all group" onclick="cinemaLocate()" title="Show in Finder">
            <div class="w-12 h-12 rounded-xl bg-white/8 backdrop-blur-sm flex items-center justify-center border border-white/15 group-hover:bg-white/18 group-hover:border-white/35 group-hover:scale-110 transition-all shadow-lg">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="text-gray-300 group-hover:text-white transition-colors">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    <polyline points="12 12 17 12 17 17"/>
                    <line x1="14" y1="10" x2="17" y2="7"/>
                </svg>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-gray-500 group-hover:text-white transition-colors">Locate</span>
        </button>

        <!-- Visual Separator -->
        <div class="w-px h-12 bg-white/8 self-start mt-0.5"></div>

        <!-- Favorite Button -->
        <button class="flex flex-col items-center gap-1.5 transition-all group" onclick="cinemaFavorite()" title="Toggle Favorite [F]">
            <div class="w-12 h-12 rounded-xl bg-arcade-gold/12 backdrop-blur-sm flex items-center justify-center border border-arcade-gold/35 group-hover:bg-arcade-gold/25 group-hover:border-arcade-gold/65 group-hover:scale-110 transition-all shadow-lg shadow-arcade-gold/10">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="text-arcade-gold group-hover:text-yellow-300 transition-colors" id="cinemaFavIcon">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-arcade-gold/75 group-hover:text-arcade-gold transition-colors">Favorite</span>
        </button>

        <!-- Tags Button -->
        <button class="flex flex-col items-center gap-1.5 transition-all group" onclick="toggleCinemaTagPanel()" title="Manage Tags">
            <div class="w-12 h-12 rounded-xl bg-arcade-cyan/12 backdrop-blur-sm flex items-center justify-center border border-arcade-cyan/35 group-hover:bg-arcade-cyan/25 group-hover:border-arcade-cyan/65 group-hover:scale-110 transition-all shadow-lg shadow-arcade-cyan/10">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="text-arcade-cyan group-hover:text-cyan-300 transition-colors">
                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
                    <line x1="7" y1="7" x2="7.01" y2="7"/>
                </svg>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-arcade-cyan/75 group-hover:text-arcade-cyan transition-colors">Tags</span>
        </button>

        <!-- Vault Button -->
        <button class="flex flex-col items-center gap-1.5 transition-all group" onclick="cinemaVault()" title="Move to Vault [V]">
            <div class="w-12 h-12 rounded-xl bg-arcade-magenta/12 backdrop-blur-sm flex items-center justify-center border border-arcade-magenta/35 group-hover:bg-arcade-magenta/25 group-hover:border-arcade-magenta/65 group-hover:scale-110 transition-all shadow-lg shadow-arcade-magenta/10">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="text-arcade-magenta group-hover:text-pink-400 transition-colors">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    <circle cx="12" cy="16" r="1" fill="currentColor"/>
                </svg>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-arcade-magenta/75 group-hover:text-arcade-magenta transition-colors">Vault</span>
        </button>

        <!-- Visual Separator -->
        <div class="w-px h-12 bg-white/8 self-start mt-0.5"></div>

        <!-- GIF Export Button -->
        <button class="flex flex-col items-center gap-1.5 transition-all group cinema-action-btn" onclick="cinemaExportGif()" title="Export as GIF [G]">
            <div class="w-12 h-12 rounded-xl bg-purple-500/12 backdrop-blur-sm flex items-center justify-center border border-purple-500/35 group-hover:bg-purple-500/25 group-hover:border-purple-500/65 group-hover:scale-110 transition-all shadow-lg shadow-purple-500/10">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="text-purple-400 group-hover:text-purple-300 transition-colors">
                    <rect x="2" y="2" width="20" height="20" rx="3"/>
                    <path d="M9 12h3v2.5a2.5 2.5 0 0 1-5 0v-5a2.5 2.5 0 0 1 5 0"/>
                    <line x1="14" y1="8" x2="14" y2="16"/>
                    <line x1="17" y1="8" x2="19" y2="8"/>
                    <line x1="17" y1="12" x2="19" y2="12"/>
                </svg>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-purple-400/75 group-hover:text-purple-400 transition-colors">GIF</span>
        </button>

        {opt_btn}
    </div>
</div>
"""


DUPLICATE_CHECKER_MODAL_COMPONENT = """
<!-- Duplicate Checker Fullscreen Modal -->
<div id="duplicateCheckerModal" class="fixed inset-0 z-50 bg-black opacity-0 pointer-events-none transition-opacity duration-300 flex flex-col">
    <!-- Active class 'opacity-100 pointer-events-auto' toggled by JS -->
    
    <!-- Close Button -->
    <button class="absolute top-6 right-6 text-white/50 hover:text-white z-50 p-2 transition-colors" onclick="closeDuplicateChecker()">
        <span class="material-icons text-4xl">close</span>
    </button>
    
    <!-- Header: Group Counter -->
    <div class="absolute top-6 left-0 right-0 text-center z-40">
        <div class="text-white/60 text-sm font-mono mb-1">DUPLICATE GROUP</div>
        <div class="text-white text-2xl font-bold tracking-wider">
            <span id="dupCheckerCurrentGroup">1</span> / <span id="dupCheckerTotalGroups">0</span>
        </div>
        <div class="text-purple-400 text-xs mt-1" id="dupCheckerGroupInfo">
            2 duplicate candidates • Qualify diff: 0.0 pts
        </div>
    </div>
    
    <!-- Main Comparison Area -->
    <div class="flex-1 flex items-center justify-center px-8 py-24">
        <div class="grid grid-cols-2 gap-8 w-full max-w-7xl">
            
            <!-- File A (Left) -->
            <div id="dupFileA" class="duplicate-file-panel flex flex-col gap-4 p-6 rounded-2xl border-2 border-white/10 bg-white/[0.02] transition-all hover:border-purple-400/50 hover:scale-[1.02]">
                <!-- Label -->
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <div class="w-10 h-10 rounded-full bg-purple-500/20 border-2 border-purple-500/50 flex items-center justify-center">
                            <span class="text-purple-400 font-bold text-lg">A</span>
                        </div>
                        <span class="text-white/60 text-sm font-semibold uppercase tracking-wide">Candidate A</span>
                    </div>
                    <div id="dupFileABadge" class="hidden px-3 py-1 rounded-full bg-green-500/20 border border-green-500/50 text-green-400 text-xs font-bold uppercase">
                        ✓ Higher Quality
                    </div>
                </div>
                
                <!-- Thumbnail -->
                <div class="relative aspect-video bg-black rounded-lg overflow-hidden cursor-pointer group" onclick="previewDuplicateFile('A')">
                    <img id="dupFileAThumb" src="" class="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity">
                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span class="material-icons text-white text-4xl drop-shadow-lg">play_circle</span>
                    </div>
                </div>
                
                <!-- Filename -->
                <div class="text-white font-medium text-sm truncate" id="dupFileAName" title="">filename_a.mp4</div>
                
                <!-- Metadata Grid -->
                <div class="grid grid-cols-2 gap-2 text-xs">
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">Quality Score</div>
                        <div id="dupFileAQuality" class="text-purple-400 font-bold text-lg">213.8</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">File Size</div>
                        <div id="dupFileASize" class="text-white font-mono">0.79 MB</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">Resolution</div>
                        <div id="dupFileARes" class="text-white font-mono">1436×1436</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">Bitrate</div>
                        <div id="dupFileABitrate" class="text-white font-mono">--</div>
                    </div>
                </div>
                
                <!-- Action Button -->
                <button onclick="keepDuplicateFile('A')" class="w-full py-3 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border-2 border-purple-500/50 hover:border-purple-500 text-purple-400 hover:text-white font-bold text-sm uppercase tracking-wider transition-all flex items-center justify-center gap-2 group">
                    <span class="material-icons">check_circle</span>
                    <span>Keep A</span>
                    <span class="text-xs opacity-60 group-hover:opacity-100">(Press 1 or ←)</span>
                </button>
            </div>
            
            <!-- File B (Right) -->
            <div id="dupFileB" class="duplicate-file-panel flex flex-col gap-4 p-6 rounded-2xl border-2 border-white/10 bg-white/[0.02] transition-all hover:border-purple-400/50 hover:scale-[1.02]">
                <!-- Label -->
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <div class="w-10 h-10 rounded-full bg-purple-500/20 border-2 border-purple-500/50 flex items-center justify-center">
                            <span class="text-purple-400 font-bold text-lg">B</span>
                        </div>
                        <span class="text-white/60 text-sm font-semibold uppercase tracking-wide">Candidate B</span>
                    </div>
                    <div id="dupFileBBadge" class="hidden px-3 py-1 rounded-full bg-green-500/20 border border-green-500/50 text-green-400 text-xs font-bold uppercase">
                        ✓ Higher Quality
                    </div>
                </div>
                
                <!-- Thumbnail -->
                <div class="relative aspect-video bg-black rounded-lg overflow-hidden cursor-pointer group" onclick="previewDuplicateFile('B')">
                    <img id="dupFileBThumb" src="" class="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity">
                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span class="material-icons text-white text-4xl drop-shadow-lg">play_circle</span>
                    </div>
                </div>
                
                <!-- Filename -->
                <div class="text-white font-medium text-sm truncate" id="dupFileBName" title="">filename_b.mp4</div>
                
                <!-- Metadata Grid -->
                <div class="grid grid-cols-2 gap-2 text-xs">
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">Quality Score</div>
                        <div id="dupFileBQuality" class="text-purple-400 font-bold text-lg">213.8</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">File Size</div>
                        <div id="dupFileBSize" class="text-white font-mono">0.79 MB</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">Resolution</div>
                        <div id="dupFileBRes" class="text-white font-mono">1436×1436</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-gray-500 mb-1">Bitrate</div>
                        <div id="dupFileBBitrate" class="text-white font-mono">--</div>
                    </div>
                </div>
                
                <!-- Action Button -->
                <button onclick="keepDuplicateFile('B')" class="w-full py-3 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border-2 border-purple-500/50 hover:border-purple-500 text-purple-400 hover:text-white font-bold text-sm uppercase tracking-wider transition-all flex items-center justify-center gap-2 group">
                    <span class="material-icons">check_circle</span>
                    <span>Keep B</span>
                    <span class="text-xs opacity-60 group-hover:opacity-100">(Press 2 or →)</span>
                </button>
            </div>
            
        </div>
    </div>
    
    <!-- Bottom Action Bar -->
    <div class="absolute bottom-8 left-0 right-0 flex items-center justify-center gap-4 z-40">
        <!-- Skip Button -->
        <button onclick="skipDuplicateGroup()" class="px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/20 hover:border-white/40 text-white/60 hover:text-white font-semibold text-sm transition-all flex items-center gap-2">
            <span class="material-icons text-lg">skip_next</span>
            <span>Skip</span>
            <span class="text-xs opacity-60">(S or Space)</span>
        </button>
        
        <!-- Any is Fine Button -->
        <button onclick="markAnyIsFine()" class="px-6 py-3 rounded-lg bg-green-500/20 hover:bg-green-500/30 border border-green-500/50 hover:border-green-500 text-green-400 hover:text-white font-semibold text-sm transition-all flex items-center gap-2">
            <span class="material-icons text-lg">done_all</span>
            <span>Any is Fine</span>
            <span class="text-xs opacity-60">(A)</span>
        </button>
    </div>
    
    <!-- Keyboard Shortcuts Legend -->
    <div class="absolute bottom-24 left-1/2 -translate-x-1/2 bg-black/80 backdrop-blur-md border border-white/10 rounded-xl px-6 py-3 z-30">
        <div class="flex items-center gap-6 text-xs text-white/60">
            <div class="flex items-center gap-2">
                <kbd class="px-2 py-1 bg-white/10 rounded font-mono font-bold text-white">1</kbd>
                <span>Keep A</span>
            </div>
            <div class="flex items-center gap-2">
                <kbd class="px-2 py-1 bg-white/10 rounded font-mono font-bold text-white">2</kbd>
                <span>Keep B</span>
            </div>
            <div class="flex items-center gap-2">
                <kbd class="px-2 py-1 bg-white/10 rounded font-mono font-bold text-white">S</kbd>
                <span>Skip</span>
            </div>
            <div class="flex items-center gap-2">
                <kbd class="px-2 py-1 bg-white/10 rounded font-mono font-bold text-white">A</kbd>
                <span>Auto</span>
            </div>
            <div class="flex items-center gap-2">
                <kbd class="px-2 py-1 bg-white/10 rounded font-mono font-bold text-white">ESC</kbd>
                <span>Exit</span>
            </div>
        </div>
    </div>
</div>
"""

TREEMAP_LEGEND_COMPONENT = """
<!-- Treemap Legend -->
<div id="treemapLegend" class="hidden w-full bg-arcade-bg/95 border-b border-white/5 py-2">
    <div class="w-full px-4 flex items-center justify-between">
        <button id="treemapBackBtn" class="hidden items-center gap-2 text-sm text-gray-400 hover:text-white" onclick="treemapZoomOut()">
            <span class="material-icons text-base">arrow_back</span> BACK
        </button>

        <div class="flex items-center gap-4 text-xs font-mono text-gray-500">
            <span class="legend-title text-white font-bold tracking-wider">STORAGE MAP</span>
            <span class="legend-hint text-arcade-cyan/70"></span>
            <div class="flex items-center gap-2 border-l border-white/10 pl-4">
                <span class="w-2 h-2 rounded-full bg-arcade-pink"></span> HIGH
                <span class="w-2 h-2 rounded-full bg-arcade-cyan"></span> OPTIMIZED
            </div>
        </div>

        <!-- Log Scale Toggle -->
        <label class="flex items-center gap-2 cursor-pointer group">
            <div class="relative w-8 h-4 bg-gray-700 rounded-full transition-colors group-hover:bg-gray-600">
                <input type="checkbox" id="treemapLogToggle" onchange="toggleTreemapScale()" class="peer sr-only">
                <div class="absolute w-3 h-3 bg-white rounded-full left-0.5 top-0.5 peer-checked:translate-x-4 transition-transform"></div>
            </div>
            <span class="text-[10px] text-gray-500 font-bold">LOG SCALE</span>
        </label>
    </div>
</div>
"""


FOLDER_BROWSER_LEGEND_COMPONENT = """
<!-- Folder Browser Legend -->
<div id="folderBrowserLegend" class="hidden w-full bg-arcade-bg/95 border-b border-white/5 py-2">
    <div class="w-full px-4 flex items-center justify-between">
        <!-- Back Button -->
        <button id="folderBrowserBackBtn" class="hidden items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors" onclick="folderBrowserBack()">
            <span class="material-icons text-base">arrow_back</span> BACK
        </button>

        <!-- Breadcrumb Navigation -->
        <div class="flex items-center gap-2 text-sm flex-1 ml-4 overflow-x-auto">
            <span class="material-icons text-arcade-cyan text-base">folder</span>
            <div id="folderBreadcrumb" class="flex items-center gap-1 font-mono">
                <!-- Populated by JS -->
            </div>
        </div>

        <!-- Videos Here Link -->
        <div id="folderVideosHereLink" class="hidden items-center gap-2 text-sm text-arcade-cyan hover:text-white cursor-pointer transition-colors" onclick="toggleFolderBrowserVideos()">
            <span class="material-icons text-base">play_circle</span>
            <span id="folderVideosHereCount">0 videos here</span>
        </div>
    </div>
</div>
"""


BATCH_BAR_COMPONENT = """
<!-- Batch Action Bar -->
<div id="batchBar" class="fixed bottom-20 md:bottom-8 left-1/2 md:left-[calc(50%+128px)] z-50 bg-[#0d0d14] border-2 border-arcade-cyan/30 rounded-2xl animate-glow-pulse glow-cyan px-4 py-2.5 flex items-center gap-2 transition-transform duration-300" style="transform: translateX(-50%) translateY(8rem);">
    <!-- Active class 'translate-y-0' handled by JS -->
    
    <!-- Select All Button -->
    <button class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold text-gray-300 hover:bg-white/10 hover:text-white transition-all" onclick="selectAllVisible()">
        <span class="material-icons text-sm">select_all</span>
        All
    </button>
    
    <div class="h-8 w-px bg-white/10"></div>
    
    <span class="text-base font-bold text-white whitespace-nowrap"><span id="batchCount" class="text-arcade-cyan text-lg">0</span> Selected</span>
    
    <div class="h-8 w-px bg-white/10"></div>
    
    <!-- TAG Button -->
    <button class="batch-action-btn" style="--btn-color: #a855f7" onclick="openBatchTagModal()">
        <span class="material-icons text-base">label</span>
        <span>TAG</span>
    </button>
    
    <!-- OPTIMIZE Button -->
    <button class="batch-action-btn" style="--btn-color: #00ffd0" onclick="triggerBatchCompress()">
        <span class="material-icons text-base">bolt</span>
        <span>OPTIMIZE</span>
    </button>
    
    <!-- FAV Button -->
    <button class="batch-action-btn" style="--btn-color: #F4B342" onclick="triggerBatchFavorite(true)">
        <span class="material-icons text-base">star</span>
        <span>FAV</span>
    </button>
    
    <!-- VAULT Button -->
    <button class="batch-action-btn" style="--btn-color: #DE1A58" onclick="triggerBatchHide(true)">
        <span class="material-icons text-base">archive</span>
        <span>VAULT</span>
    </button>
    
    <!-- DELETE Button -->
    <button class="batch-action-btn" style="--btn-color: #EF4444" onclick="triggerBatchDelete()">
        <span class="material-icons text-base">delete_forever</span>
        <span>DELETE</span>
    </button>
    
    <div class="h-8 w-px bg-white/10"></div>
    
    <button class="text-gray-400 hover:text-white transition-colors p-1" onclick="clearSelection()" title="Clear Selection">
        <span class="material-icons text-xl">close</span>
    </button>
</div>

<style>
.batch-action-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.875rem;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--btn-color, white);
    background: color-mix(in srgb, var(--btn-color, white) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--btn-color, white) 30%, transparent);
    transition: all 0.2s;
    cursor: pointer;
}
.batch-action-btn:hover {
    background: color-mix(in srgb, var(--btn-color, white) 25%, transparent);
    color: white;
    transform: translateY(-1px);
}
</style>
"""


FOLDER_SIDEBAR_COMPONENT = """
<!-- Folder Sidebar (Off-Canvas) -->
<div id="folderSidebar" class="fixed inset-y-0 left-0 w-80 bg-[#101018]/95 backdrop-blur-xl border-r border-white/10 transform -translate-x-full transition-transform duration-300 z-30 flex flex-col pt-safe-top">
    <!-- Active class 'translate-x-0' handled by JS -->
    
    <div class="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 class="font-bold text-white tracking-wider">FOLDERS</h3>
        <button class="text-gray-400 hover:text-white" onclick="toggleFolderSidebar()">
            <span class="material-icons">close</span>
        </button>
    </div>
    
    <div id="folderList" class="flex-1 overflow-y-auto p-2 space-y-1">
        <!-- Injected by JS -->
    </div>
</div>
"""

SAVED_VIEWS_COMPONENT = """
<!-- Saved Views Chips -->
<div id="savedViewsContainer" class="hidden md:flex flex-wrap gap-2 px-6 pb-2 items-center">
    <!-- Injected by JS -->
</div>
"""

FILTER_PANEL_COMPONENT = """
<!-- Filter Panel (Drawer on Desktop, Bottom Sheet on Mobile) -->
<div id="filterPanel" class="fixed inset-0 z-40 hidden">
    <!-- Backdrop -->
    <div id="filterPanelBackdrop" class="absolute inset-0 bg-black/60 opacity-0 transition-opacity duration-300" onclick="closeFilterPanel()"></div>
    
    <!-- Panel Content -->
    <div id="filterPanelContent" class="absolute bg-arcade-bg/98 dark:bg-[#12121a]/95 backdrop-blur-xl border-black/10 dark:border-white/10 shadow-2xl transition-transform duration-300 flex flex-col overflow-hidden
        right-0 top-0 bottom-0 w-80 translate-x-full rounded-l-2xl border-l">
        
        <!-- Header -->
        <div class="p-4 border-b border-white/5 flex items-center justify-between shrink-0">
            <div class="flex items-center gap-3">
                <span class="material-icons text-arcade-cyan">tune</span>
                <h2 class="font-semibold text-white">Filters</h2>
                <span id="filterPanelCount" class="text-xs text-gray-500">(0 active)</span>
            </div>
            <button onclick="closeFilterPanel()" class="text-gray-500 hover:text-white p-1">
                <span class="material-icons">close</span>
            </button>
        </div>
        
        <!-- Scrollable Body -->
        <div class="flex-1 overflow-y-auto p-4 space-y-6">
            
            <!-- SIZE Section -->
            <section>
                <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Filesize (MB)</h3>
                <div class="flex items-center gap-2">
                    <div class="relative flex-1">
                        <input type="number" id="filterMinSize" placeholder="Min" class="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none" onchange="setMinSize(this.value)">
                        <span class="absolute right-2 top-2 text-xs text-gray-500 pointer-events-none">MB</span>
                    </div>
                    <span class="text-gray-500">-</span>
                    <div class="relative flex-1">
                        <input type="number" id="filterMaxSize" placeholder="Max" class="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none" onchange="setMaxSize(this.value)">
                        <span class="absolute right-2 top-2 text-xs text-gray-500 pointer-events-none">MB</span>
                    </div>
                </div>
            </section>

            <!-- DATE Section -->
            <section>
                <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Import Date</h3>
                <div class="flex flex-wrap gap-2">
                    <button class="filter-chip active" data-filter="date" data-value="all" onclick="setDateFilter('all')">
                        All Time
                    </button>
                    <button class="filter-chip" data-filter="date" data-value="1d" onclick="setDateFilter('1d')">
                        Last 24h
                    </button>
                    <button class="filter-chip" data-filter="date" data-value="7d" onclick="setDateFilter('7d')">
                        Last 7d
                    </button>
                    <button class="filter-chip" data-filter="date" data-value="30d" onclick="setDateFilter('30d')">
                        Last 30d
                    </button>
                </div>
            </section>

            <!-- STATUS Section -->
            <!-- STATUS Section -->
            <section>
                <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Status</h3>
                <div class="flex flex-wrap gap-2">
                    <button class="filter-chip active" data-filter="status" data-value="all" onclick="setFilterOption('status', 'all')">
                        All
                    </button>
                    <button class="filter-chip" data-filter="status" data-value="SOURCE" onclick="setFilterOption('status', 'SOURCE')">
                        Source (Raw)
                    </button>
                    <button class="filter-chip" data-filter="status" data-value="HIGH" onclick="setFilterOption('status', 'HIGH')">
                        High Bitrate
                    </button>
                     <button class="filter-chip" data-filter="status" data-value="OK" onclick="setFilterOption('status', 'OK')">
                        OK
                    </button>
                    <button class="filter-chip" data-filter="status" data-value="optimized_files" onclick="setFilterOption('status', 'optimized_files')">
                        Optimized
                    </button>
                </div>
            </section>
            
            <!-- CODEC Section -->
            <section>
                <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Codec</h3>
                <div class="flex flex-wrap gap-2">
                    <button class="filter-chip active" data-filter="codec" data-value="all" onclick="setFilterOption('codec', 'all')">
                        All
                    </button>
                    <button class="filter-chip" data-filter="codec" data-value="hevc" onclick="setFilterOption('codec', 'hevc')">
                        HEVC / H.265
                    </button>
                    <button class="filter-chip" data-filter="codec" data-value="h264" onclick="setFilterOption('codec', 'h264')">
                        H.264
                    </button>
                    <button class="filter-chip" data-filter="codec" data-value="av1" onclick="setFilterOption('codec', 'av1')">
                        AV1
                    </button>
                </div>
            </section>
            
            <!-- TAGS Section -->
            <section>
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest">Tags</h3>
                    <button onclick="openTagManager()" class="text-xs text-arcade-cyan hover:text-cyan-300 flex items-center gap-1">
                        <span class="material-icons text-sm">add</span> Manage
                    </button>
                </div>
                <div id="filterTagsList" class="flex flex-wrap gap-2">
                    <!-- Tag chips injected by JS -->
                    <span class="text-xs text-gray-600 italic">No tags created yet</span>
                </div>
                
                <!-- Untagged Toggle -->
                <label class="flex items-center gap-2 mt-4 cursor-pointer group">
                    <input type="checkbox" id="filterUntaggedOnly" onchange="toggleUntaggedFilter()" class="sr-only peer">
                    <div class="w-5 h-5 rounded border border-white/20 flex items-center justify-center peer-checked:bg-arcade-cyan peer-checked:border-arcade-cyan transition-colors">
                        <span class="material-icons text-sm text-black opacity-0 peer-checked:opacity-100">check</span>
                    </div>
                    <span class="text-sm text-gray-400 group-hover:text-white transition-colors">Show untagged only</span>
                </label>
            </section>
            
        </div>
        
        <!-- Footer -->
        <div class="p-4 border-t border-black/5 dark:border-white/5 flex items-center justify-between shrink-0 bg-black/5 dark:bg-[#0a0a12]">
            <button onclick="resetFilters()" class="text-sm text-gray-500 hover:text-white transition-colors">
                Reset all
            </button>
            <button onclick="applyFilters()" class="px-6 py-2 bg-arcade-cyan text-black font-bold rounded-lg hover:bg-cyan-300 transition-colors shadow-lg shadow-arcade-cyan/20">
                Apply
            </button>
        </div>
    </div>
</div>

<style>
    /* Filter Panel States */
    #filterPanel.active { display: block !important; }
    #filterPanel.active #filterPanelBackdrop { opacity: 1; }
    #filterPanel.active #filterPanelContent { transform: translateX(0); }
    
    /* Filter Chip Styles */
    .filter-chip {
        padding: 0.375rem 0.875rem;
        font-size: 0.75rem;
        border-radius: 9999px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #9ca3af;
        transition: all 0.2s;
        cursor: pointer;
    }
    .filter-chip:hover {
        background: rgba(255, 255, 255, 0.1);
        color: white;
    }
    .filter-chip.active {
        background: rgba(0, 255, 208, 0.15);
        border-color: rgba(0, 255, 208, 0.5);
        color: #00ffd0;
    }
    
    /* Tag Filter Chips */
    .tag-filter-chip {
        padding: 0.375rem 0.75rem;
        font-size: 0.75rem;
        border-radius: 9999px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #d1d5db;
        transition: all 0.2s;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 0.375rem;
    }
    .tag-filter-chip:hover {
        border-color: rgba(255, 255, 255, 0.3);
    }
    .tag-filter-chip.active {
        border-width: 2px;
    }
    .tag-filter-chip .tag-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    .tag-filter-chip.negative {
        background: rgba(239, 68, 68, 0.15);
        border-color: rgba(239, 68, 68, 0.5);
        color: #fca5a5;
        text-decoration: line-through;
    }
    .tag-filter-chip.negative .tag-dot {
        background-color: #ef4444 !important;
    }
</style>
"""

TAG_MANAGER_MODAL_COMPONENT = """
<!-- Tag Manager Modal -->
<div id="tagManagerModal" class="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm hidden opacity-0 transition-opacity duration-300 flex items-center justify-center p-4">
    <div class="w-full max-w-md bg-[#1a1a24] rounded-2xl shadow-2xl border border-white/10 transform scale-95 transition-transform duration-300 overflow-hidden">
        
        <!-- Header -->
        <div class="p-4 border-b border-white/5 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <span class="material-icons text-arcade-gold">label</span>
                <h2 class="font-semibold text-white">Manage Tags</h2>
            </div>
            <button onclick="closeTagManager()" class="text-gray-500 hover:text-white p-1">
                <span class="material-icons">close</span>
            </button>
        </div>
        
        <!-- Create New Tag -->
        <div class="p-4 border-b border-white/5 bg-[#12121a]">
            <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Create New Tag</h3>
            <div class="flex gap-2">
                <input type="text" id="newTagName" placeholder="Tag name..." class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none">
                                <!-- Color Picker -->
                            <div class="relative">
                                <button type="button" id="tagColorBtn" class="w-10 h-10 rounded-lg border-2 border-white/20 hover:border-white/40 transition-colors" style="background-color: #00ffd0" onclick="toggleTagColorPicker()"></button>
                                <input type="hidden" id="newTagColor" value="#00ffd0">
                                <div id="tagColorPicker" class="hidden absolute bottom-full left-0 mb-2 p-2 bg-[#1a1a24] rounded-lg border border-white/10 flex gap-2 flex-wrap w-40 z-50">
                                    <button type="button" class="w-6 h-6 rounded" style="background: #00ffd0" onclick="selectTagColor('#00ffd0')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #ff6b9d" onclick="selectTagColor('#ff6b9d')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #a855f7" onclick="selectTagColor('#a855f7')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #eab308" onclick="selectTagColor('#eab308')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #ef4444" onclick="selectTagColor('#ef4444')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #22c55e" onclick="selectTagColor('#22c55e')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #3b82f6" onclick="selectTagColor('#3b82f6')"></button>
                                    <button type="button" class="w-6 h-6 rounded" style="background: #f97316" onclick="selectTagColor('#f97316')"></button>
                                </div>
                            </div>
                            
                            <!-- Shortcut Key -->
                            <input type="text" id="newTagShortcut" 
                                   placeholder="Key" 
                                   maxlength="1"
                                   class="w-12 px-2 py-2 bg-black/40 border border-white/10 rounded-lg text-white text-center uppercase focus:outline-none focus:border-arcade-cyan/50"
                                   title="Cinema mode keyboard shortcut (A-Z, except F and V)">
                            
                            <button type="button" onclick="createNewTag()" class="px-4 py-2 bg-arcade-cyan/20 text-arcade-cyan rounded-lg hover:bg-arcade-cyan/30 transition-colors text-sm font-medium">
                                Add
                            </button>
            </div>
        </div>
        
        <!-- Existing Tags List -->
        <div class="p-4 max-h-64 overflow-y-auto">
            <h3 id="manageTagsHeader" class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Manage Existing Tags</h3>
            <div id="existingTagsList" class="space-y-2">
                <!-- Tags injected by JS -->
                <p class="text-sm text-gray-600 italic">No tags created yet</p>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="p-4 border-t border-white/5 bg-[#0a0a12]">
            <button onclick="closeTagManager()" class="w-full py-2 bg-white/5 text-gray-400 font-medium rounded-lg hover:bg-white/10 hover:text-white transition-colors">
                Done
            </button>
        </div>
    </div>
</div>

<style>
    #tagManagerModal.active { display: flex !important; opacity: 1; }
    #tagManagerModal.active > div { transform: scale(1); }
</style>
"""

COLLECTION_MODAL_COMPONENT = """
<!-- Collection Manager Modal -->
<div id="collectionModal" class="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm hidden opacity-0 transition-opacity duration-300 flex items-center justify-center p-4">
    <div class="bg-[#101018] border border-white/10 rounded-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh] animate-glow-pulse glow-cyan">

        <!-- Header -->
        <div class="p-4 border-b border-white/5 flex items-center justify-between shrink-0">
            <div class="flex items-center gap-3">
                <span class="material-icons text-arcade-cyan">auto_awesome</span>
                <h2 id="collectionModalTitle" class="font-semibold text-white">New Collection</h2>
                <span class="text-xs text-gray-600 ml-2 hidden sm:inline">Press <kbd class="px-1 py-0.5 bg-white/5 rounded text-[10px]">ESC</kbd> to close</span>
            </div>
            <button onclick="closeCollectionModal()" class="text-gray-500 hover:text-white p-1 hover:bg-white/5 rounded transition-colors" aria-label="Close dialog">
                <span class="material-icons">close</span>
            </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto p-4" style="max-height: calc(90vh - 180px);">

            <!-- Appearance Section (Always Visible) -->
            <section class="mb-4">
                <h3 class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Appearance</h3>
                <div class="flex gap-3">
                    <input type="text" id="collectionName" placeholder="Collection name..."
                           class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors">

                    <!-- Icon Picker -->
                    <div class="relative">
                        <button id="collectionIconBtn" onclick="toggleCollectionIconPicker()"
                                class="w-10 h-10 rounded-lg border border-white/10 flex items-center justify-center hover:border-arcade-cyan/30 hover:bg-white/5 transition-colors bg-black/40"
                                aria-label="Choose icon">
                            <span class="material-icons text-arcade-cyan" id="selectedCollectionIcon">folder_special</span>
                        </button>
                        <div id="collectionIconPicker" class="hidden absolute right-0 top-12 bg-[#1a1a24] border border-white/10 rounded-lg p-2 shadow-xl z-10 grid grid-cols-5 gap-1 w-48">
                            <button onclick="selectCollectionIcon('movie')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Movie icon"><span class="material-icons text-sm">movie</span></button>
                            <button onclick="selectCollectionIcon('photo_library')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Photo library icon"><span class="material-icons text-sm">photo_library</span></button>
                            <button onclick="selectCollectionIcon('folder_special')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Special folder icon"><span class="material-icons text-sm">folder_special</span></button>
                            <button onclick="selectCollectionIcon('star')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Star icon"><span class="material-icons text-sm">star</span></button>
                            <button onclick="selectCollectionIcon('favorite')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Favorite icon"><span class="material-icons text-sm">favorite</span></button>
                            <button onclick="selectCollectionIcon('bolt')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Bolt icon"><span class="material-icons text-sm">bolt</span></button>
                            <button onclick="selectCollectionIcon('whatshot')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Hot icon"><span class="material-icons text-sm">whatshot</span></button>
                            <button onclick="selectCollectionIcon('visibility')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Visibility icon"><span class="material-icons text-sm">visibility</span></button>
                            <button onclick="selectCollectionIcon('schedule')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Schedule icon"><span class="material-icons text-sm">schedule</span></button>
                            <button onclick="selectCollectionIcon('category')" class="p-2 hover:bg-arcade-cyan/10 rounded transition-colors" aria-label="Category icon"><span class="material-icons text-sm">category</span></button>
                        </div>
                    </div>

                    <!-- Color Picker -->
                    <div class="relative">
                        <button id="collectionColorBtn" onclick="toggleCollectionColorPicker()"
                                class="w-10 h-10 rounded-lg border-2 border-white/20 flex items-center justify-center hover:border-white/40 hover:scale-105 transition-all shadow-lg"
                                style="background-color: #00ffd0;"
                                aria-label="Choose color">
                        </button>
                        <input type="hidden" id="collectionColor" value="#00ffd0">
                        <div id="collectionColorPicker" class="hidden absolute right-0 top-12 bg-[#1a1a24] border border-white/10 rounded-lg p-3 shadow-xl z-50 grid grid-cols-5 gap-2 w-64">
                            <button onclick="selectCollectionColor('#00ffd0')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #00ffd0;" aria-label="Cyan color"></button>
                            <button onclick="selectCollectionColor('#F4B342')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #F4B342;" aria-label="Orange color"></button>
                            <button onclick="selectCollectionColor('#DE1A58')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #DE1A58;" aria-label="Red color"></button>
                            <button onclick="selectCollectionColor('#8F0177')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #8F0177;" aria-label="Purple color"></button>
                            <button onclick="selectCollectionColor('#6366f1')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #6366f1;" aria-label="Indigo color"></button>
                            <button onclick="selectCollectionColor('#22c55e')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #22c55e;" aria-label="Green color"></button>
                            <button onclick="selectCollectionColor('#f97316')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #f97316;" aria-label="Bright orange color"></button>
                            <button onclick="selectCollectionColor('#06b6d4')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #06b6d4;" aria-label="Teal color"></button>
                            <button onclick="selectCollectionColor('#ec4899')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #ec4899;" aria-label="Pink color"></button>
                            <button onclick="selectCollectionColor('#a855f7')" class="w-8 h-8 rounded-md hover:scale-110 transition-transform ring-2 ring-white/20" style="background-color: #a855f7;" aria-label="Violet color"></button>
                        </div>
                    </div>
                </div>

                <!-- Category Selector -->
                <div class="mt-3">
                    <label for="collectionCategory" class="text-xs text-gray-400 mb-1.5 block">Category (for sidebar grouping)</label>
                    <div class="flex gap-2">
                        <select id="collectionCategory"
                                class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                                onchange="handleCategoryChange(this)">
                            <option value="">Uncategorized</option>
                            <!-- Populated by JS -->
                        </select>
                        <input type="text" id="newCategoryInput"
                               placeholder="New category..."
                               class="hidden flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                               aria-label="New category name">
                        <button onclick="toggleNewCategoryInput()"
                                id="addCategoryBtn"
                                class="px-3 py-1.5 text-arcade-cyan hover:text-cyan-300 border border-white/10 rounded-lg hover:border-arcade-cyan/30 hover:bg-arcade-cyan/5 transition-colors"
                                title="Add new category"
                                aria-label="Add new category">
                            <span class="material-icons text-sm">add</span>
                        </button>
                    </div>
                </div>
            </section>

            <!-- Filter Rules - Accordion Layout -->
            <div class="space-y-2">

                <!-- Properties Accordion -->
                <div class="border border-white/5 rounded-lg overflow-hidden">
                    <button onclick="toggleFilterAccordion('properties')"
                            class="w-full flex items-center justify-between p-3 bg-black/20 hover:bg-black/30 transition-colors group"
                            aria-expanded="false"
                            aria-controls="propertiesPanel">
                        <div class="flex items-center gap-2">
                            <span class="material-icons text-sm text-gray-400 group-hover:text-arcade-cyan transition-all duration-200" id="propertiesChevron">expand_more</span>
                            <span class="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">Properties</span>
                            <span class="text-xs text-gray-500">Media Type, Status, Format...</span>
                        </div>
                        <span id="propertiesBadge" class="hidden px-2 py-0.5 rounded-full bg-arcade-cyan/20 text-arcade-cyan text-xs font-medium"></span>
                    </button>
                    <div id="propertiesPanel" class="hidden" role="region">
                        <div class="p-3 space-y-3 bg-black/10">

                            <!-- Media Type -->
                            <div>
                                <label class="text-xs text-gray-400 mb-1.5 block">Media Type</label>
                                <div class="flex flex-wrap gap-1.5">
                                    <button class="filter-chip" data-filter="media_type" data-value="video" onclick="toggleSmartFilterChip(this)" aria-pressed="false">
                                        <span class="material-icons text-xs">movie</span>Videos
                                    </button>
                                    <button class="filter-chip" data-filter="media_type" data-value="image" onclick="toggleSmartFilterChip(this)" aria-pressed="false">
                                        <span class="material-icons text-xs">image</span>Images
                                    </button>
                                </div>
                            </div>

                            <!-- Status -->
                            <div>
                                <label class="text-xs text-gray-400 mb-1.5 block">Status</label>
                                <div class="flex flex-wrap gap-1.5">
                                    <button class="filter-chip" data-filter="status" data-value="HIGH" onclick="toggleSmartFilterChip(this)" aria-pressed="false">High Bitrate</button>
                                    <button class="filter-chip" data-filter="status" data-value="OK" onclick="toggleSmartFilterChip(this)" aria-pressed="false">OK</button>
                                    <button class="filter-chip" data-filter="status" data-value="optimized_files" onclick="toggleSmartFilterChip(this)" aria-pressed="false">Optimized</button>
                                </div>
                            </div>

                            <!-- Advanced Technical Filters (Collapsible) -->
                            <details class="group/details">
                                <summary class="cursor-pointer text-xs text-arcade-cyan hover:text-cyan-300 flex items-center gap-1 py-1.5 list-none select-none">
                                    <span class="material-icons text-xs group-open/details:rotate-90 transition-transform">chevron_right</span>
                                    Advanced technical filters
                                </summary>
                                <div class="mt-3 space-y-3 pl-4 border-l-2 border-white/5">

                                    <!-- Codec -->
                                    <div>
                                        <label class="text-xs text-gray-400 mb-1.5 block">Codec</label>
                                        <div class="flex flex-wrap gap-1.5">
                                            <button class="filter-chip" data-filter="codec" data-value="hevc" onclick="toggleSmartFilterChip(this)" aria-pressed="false">HEVC</button>
                                            <button class="filter-chip" data-filter="codec" data-value="h264" onclick="toggleSmartFilterChip(this)" aria-pressed="false">H.264</button>
                                            <button class="filter-chip" data-filter="codec" data-value="vp9" onclick="toggleSmartFilterChip(this)" aria-pressed="false">VP9</button>
                                            <button class="filter-chip" data-filter="codec" data-value="av1" onclick="toggleSmartFilterChip(this)" aria-pressed="false">AV1</button>
                                        </div>
                                    </div>

                                    <!-- Resolution -->
                                    <div>
                                        <label class="text-xs text-gray-400 mb-1.5 block">Resolution</label>
                                        <div class="flex flex-wrap gap-1.5">
                                            <button class="filter-chip" data-filter="resolution" data-value="4k" onclick="toggleSmartFilterChip(this)" aria-pressed="false">4K</button>
                                            <button class="filter-chip" data-filter="resolution" data-value="1080p" onclick="toggleSmartFilterChip(this)" aria-pressed="false">1080p</button>
                                            <button class="filter-chip" data-filter="resolution" data-value="720p" onclick="toggleSmartFilterChip(this)" aria-pressed="false">720p</button>
                                            <button class="filter-chip" data-filter="resolution" data-value="sd" onclick="toggleSmartFilterChip(this)" aria-pressed="false">SD</button>
                                        </div>
                                    </div>

                                    <!-- Orientation -->
                                    <div>
                                        <label class="text-xs text-gray-400 mb-1.5 block">Orientation</label>
                                        <div class="flex flex-wrap gap-1.5">
                                            <button class="filter-chip" data-filter="orientation" data-value="landscape" onclick="toggleSmartFilterChip(this)" aria-pressed="false">
                                                <span class="material-icons text-xs">crop_landscape</span>Landscape
                                            </button>
                                            <button class="filter-chip" data-filter="orientation" data-value="portrait" onclick="toggleSmartFilterChip(this)" aria-pressed="false">
                                                <span class="material-icons text-xs">crop_portrait</span>Portrait
                                            </button>
                                            <button class="filter-chip" data-filter="orientation" data-value="square" onclick="toggleSmartFilterChip(this)" aria-pressed="false">
                                                <span class="material-icons text-xs">crop_square</span>Square
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Format (Images) -->
                                    <div>
                                        <label class="text-xs text-gray-400 mb-1.5 block">Format</label>

                                        <!-- Common formats -->
                                        <div class="flex flex-wrap gap-1.5 mb-2">
                                            <button class="filter-chip" data-filter="format" data-value="jpg" onclick="toggleSmartFilterChip(this)" aria-pressed="false">JPG</button>
                                            <button class="filter-chip" data-filter="format" data-value="png" onclick="toggleSmartFilterChip(this)" aria-pressed="false">PNG</button>
                                            <button class="filter-chip" data-filter="format" data-value="gif" onclick="toggleSmartFilterChip(this)" aria-pressed="false">GIF</button>
                                            <button class="filter-chip" data-filter="format" data-value="webp" onclick="toggleSmartFilterChip(this)" aria-pressed="false">WebP</button>
                                            <button class="filter-chip" data-filter="format" data-value="heic" onclick="toggleSmartFilterChip(this)" aria-pressed="false">HEIC</button>
                                            <button class="filter-chip" data-filter="format" data-value="avif" onclick="toggleSmartFilterChip(this)" aria-pressed="false">AVIF</button>
                                        </div>

                                        <!-- RAW formats (nested collapse) -->
                                        <details class="group/raw">
                                            <summary class="cursor-pointer text-xs text-gray-400 hover:text-arcade-cyan flex items-center gap-1 py-1 list-none select-none">
                                                <span class="material-icons text-xs group-open/raw:rotate-90 transition-transform">chevron_right</span>
                                                RAW formats
                                            </summary>
                                            <div class="flex flex-wrap gap-1.5 mt-2 pl-4">
                                                <button class="filter-chip" data-filter="format" data-value="cr2" onclick="toggleSmartFilterChip(this)" aria-pressed="false">CR2</button>
                                                <button class="filter-chip" data-filter="format" data-value="dng" onclick="toggleSmartFilterChip(this)" aria-pressed="false">DNG</button>
                                                <button class="filter-chip" data-filter="format" data-value="raf" onclick="toggleSmartFilterChip(this)" aria-pressed="false">RAF</button>
                                                <button class="filter-chip" data-filter="format" data-value="nef" onclick="toggleSmartFilterChip(this)" aria-pressed="false">NEF</button>
                                                <button class="filter-chip" data-filter="format" data-value="arw" onclick="toggleSmartFilterChip(this)" aria-pressed="false">ARW</button>
                                            </div>
                                        </details>
                                    </div>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>

                <!-- Content & Metadata Accordion -->
                <div class="border border-white/5 rounded-lg overflow-hidden">
                    <button onclick="toggleFilterAccordion('metadata')"
                            class="w-full flex items-center justify-between p-3 bg-black/20 hover:bg-black/30 transition-colors group"
                            aria-expanded="false"
                            aria-controls="metadataPanel">
                        <div class="flex items-center gap-2">
                            <span class="material-icons text-sm text-gray-400 group-hover:text-arcade-cyan transition-all duration-200" id="metadataChevron">expand_more</span>
                            <span class="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">Content & Metadata</span>
                            <span class="text-xs text-gray-500">Date, Size, Favorites, Tags...</span>
                        </div>
                        <span id="metadataBadge" class="hidden px-2 py-0.5 rounded-full bg-arcade-cyan/20 text-arcade-cyan text-xs font-medium"></span>
                    </button>
                    <div id="metadataPanel" class="hidden" role="region">
                        <div class="p-3 space-y-3 bg-black/10">

                            <!-- Import Date -->
                            <div>
                                <label for="collectionDateFilter" class="text-xs text-gray-400 mb-1.5 block">Import Date</label>
                                <select id="collectionDateFilter" class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors" onchange="updateCollectionPreviewCount(); updateFilterSectionBadge('metadata');">
                                    <option value="all">Any Time</option>
                                    <option value="1d">Last 24 Hours</option>
                                    <option value="7d">Last 7 Days</option>
                                    <option value="30d">Last 30 Days</option>
                                    <option value="90d">Last 3 Months</option>
                                    <option value="1y">Last Year</option>
                                </select>
                            </div>

                            <!-- File Size -->
                            <div>
                                <label class="text-xs text-gray-400 mb-1.5 block">File Size (MB)</label>
                                <div class="flex items-center gap-2">
                                    <input type="number" id="collectionMinSize" placeholder="Min"
                                           class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                                           oninput="updateCollectionPreviewCount(); updateFilterSectionBadge('metadata');"
                                           aria-label="Minimum file size in megabytes">
                                    <span class="text-gray-500 text-xs">-</span>
                                    <input type="number" id="collectionMaxSize" placeholder="Max"
                                           class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                                           oninput="updateCollectionPreviewCount(); updateFilterSectionBadge('metadata');"
                                           aria-label="Maximum file size in megabytes">
                                </div>
                            </div>

                            <!-- Duration (Runtime) -->
                            <div>
                                <label class="text-xs text-gray-400 mb-1.5 block">Runtime (Seconds)</label>
                                <div class="flex items-center gap-2">
                                    <input type="number" id="collectionMinDuration" placeholder="Min"
                                           class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                                           oninput="updateCollectionPreviewCount(); updateFilterSectionBadge('metadata');"
                                           aria-label="Minimum duration in seconds">
                                    <span class="text-gray-500 text-xs">-</span>
                                    <input type="number" id="collectionMaxDuration" placeholder="Max"
                                           class="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                                           oninput="updateCollectionPreviewCount(); updateFilterSectionBadge('metadata');"
                                           aria-label="Maximum duration in seconds">
                                </div>
                            </div>

                            <!-- Favorites -->
                            <div>
                                <label class="text-xs text-gray-400 mb-1.5 block">Favorites</label>
                                <div class="flex gap-1.5">
                                    <button class="filter-chip" data-filter="favorites" data-value="true" onclick="setFavoritesFilter(true)" aria-pressed="false">Only Favorites</button>
                                    <button class="filter-chip" data-filter="favorites" data-value="false" onclick="setFavoritesFilter(false)" aria-pressed="false">Exclude</button>
                                    <button class="filter-chip active" data-filter="favorites" data-value="null" onclick="setFavoritesFilter(null)" aria-pressed="true">Any</button>
                                </div>
                            </div>

                            <!-- Tags (Tri-State) -->
                            <div>
                                <div class="flex justify-between items-center mb-1.5">
                                    <label class="text-xs text-gray-400">Tags</label>
                                    <div class="flex items-center gap-1 text-[10px]">
                                        <span class="text-gray-600">Match:</span>
                                        <button id="tagLogicBtn" onclick="toggleTagLogic()" class="px-2 py-0.5 rounded bg-arcade-cyan/20 text-arcade-cyan font-medium hover:bg-arcade-cyan/30 transition-colors" aria-label="Toggle tag matching logic">ANY</button>
                                    </div>
                                </div>
                                <div id="collectionTagsList" class="flex flex-wrap gap-1.5 min-h-[28px]">
                                    <span class="text-xs text-gray-600 italic">No tags created</span>
                                </div>
                            </div>

                            <!-- Search Term -->
                            <div>
                                <label for="collectionSearch" class="text-xs text-gray-400 mb-1.5 block">Search Term</label>
                                <input type="text" id="collectionSearch" placeholder="Filter by filename..."
                                       class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder:text-gray-600 focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/20 transition-colors"
                                       oninput="updateCollectionPreviewCount(); updateFilterSectionBadge('metadata');">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </div>

        <!-- Footer with Count Badge -->
        <div class="p-4 border-t border-white/5 flex items-center justify-between shrink-0 bg-[#0a0a12]">
            <div class="flex items-center gap-3">
                <span class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-arcade-cyan/10 text-arcade-cyan text-sm font-medium">
                    <span class="material-icons text-sm" id="matchCountIcon">movie</span>
                    <span id="matchCountNumber">0</span> <span id="matchCountLabel">items</span>
                </span>
                <button id="deleteCollectionBtn" onclick="deleteCurrentCollection()" class="hidden text-sm text-red-400 hover:text-red-300 hover:bg-red-400/10 px-2 py-1 rounded transition-colors">
                    <span class="material-icons text-sm align-middle mr-1">delete</span>Delete
                </button>
            </div>
            <div class="flex gap-3">
                <button onclick="closeCollectionModal()" class="px-4 py-2 bg-white/5 text-gray-400 font-medium rounded-lg hover:bg-white/10 hover:text-white transition-colors">
                    Cancel
                </button>
                <button onclick="saveCollection()" class="px-6 py-2 bg-arcade-cyan text-black font-bold rounded-lg hover:bg-cyan-300 transition-all shadow-lg shadow-arcade-cyan/20 hover:shadow-arcade-cyan/30">
                    Save
                </button>
            </div>
        </div>
    </div>
</div>

<style>
    #collectionModal.active { display: flex !important; opacity: 1; }
    #collectionModal.active > div { transform: scale(1); }

    /* Custom scrollbar for modal */
    #collectionModal .overflow-y-auto::-webkit-scrollbar {
        width: 8px;
    }
    #collectionModal .overflow-y-auto::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
    }
    #collectionModal .overflow-y-auto::-webkit-scrollbar-thumb {
        background: rgba(100, 255, 218, 0.2);
        border-radius: 4px;
    }
    #collectionModal .overflow-y-auto::-webkit-scrollbar-thumb:hover {
        background: rgba(100, 255, 218, 0.3);
    }
    #collectionModal .overflow-y-auto {
        scrollbar-width: thin;
        scrollbar-color: rgba(100, 255, 218, 0.2) rgba(0, 0, 0, 0.2);
    }

    /* Legacy chip styles */
    .collection-filter-chip {
        padding: 0.375rem 0.875rem;
        font-size: 0.75rem;
        border-radius: 9999px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #9ca3af;
        transition: all 0.2s;
        cursor: pointer;
    }
    .collection-filter-chip:hover {
        background: rgba(255, 255, 255, 0.1);
        color: white;
    }
    .collection-filter-chip.active {
        background: rgba(0, 255, 208, 0.15);
        border-color: rgba(0, 255, 208, 0.5);
        color: #00ffd0;
    }

    /* Filter chip styles for Smart Collection */
    .filter-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.25rem 0.625rem;
        font-size: 0.6875rem;
        font-weight: 500;
        line-height: 1.4;
        border-radius: 0.375rem;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #9ca3af;
        transition: all 0.15s ease;
        cursor: pointer;
        white-space: nowrap;
    }
    .filter-chip:hover {
        background: rgba(255, 255, 255, 0.1);
        color: white;
        border-color: rgba(255, 255, 255, 0.2);
    }
    .filter-chip.active {
        background: rgba(100, 255, 218, 0.15);
        border-color: rgba(100, 255, 218, 0.4);
        color: #64FFDA;
    }
    .filter-chip.exclude {
        background: rgba(239, 68, 68, 0.15);
        border-color: rgba(239, 68, 68, 0.4);
        color: #ef4444;
    }
    .filter-chip .material-icons {
        font-size: 0.875rem;
    }
</style>
"""

HIDDEN_PATH_MODAL_COMPONENT = """
<!-- Hidden Path Helper Modal -->
<div id="hiddenPathModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden opacity-0 transition-opacity duration-300 flex items-center justify-center p-4">
    <div class="w-full max-w-lg bg-[#1a1a24] rounded-2xl shadow-2xl border border-white/10 transform scale-95 transition-transform duration-300 overflow-hidden">

        <!-- Header -->
        <div class="p-4 border-b border-white/5 flex items-center gap-3">
            <span class="material-icons text-amber-400">folder_off</span>
            <h2 class="font-semibold text-white">File in Hidden Folder</h2>
        </div>

        <!-- Body -->
        <div class="p-5 space-y-4">
            <p class="text-sm text-gray-400">
                This file is located in a hidden system folder and cannot be revealed directly.
                You can copy the path below and navigate to it manually.
            </p>

            <!-- Path Display -->
            <div class="bg-black/40 rounded-lg p-3 border border-white/10">
                <label class="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Full Path</label>
                <code id="hiddenPathDisplay" class="text-xs text-arcade-cyan break-all select-all block"></code>
            </div>

            <!-- Copy Button -->
            <button onclick="copyHiddenPath()" class="w-full py-2.5 rounded-lg bg-arcade-cyan/10 text-arcade-cyan hover:bg-arcade-cyan/20 border border-arcade-cyan/30 text-sm font-medium transition-all flex items-center justify-center gap-2">
                <span class="material-icons text-sm" id="copyPathIcon">content_copy</span>
                <span id="copyPathText">Copy Path to Clipboard</span>
            </button>

            <!-- Finder Tip -->
            <div class="bg-amber-500/10 rounded-lg p-3 border border-amber-500/20">
                <div class="flex items-start gap-2">
                    <span class="material-icons text-amber-400 text-sm mt-0.5">lightbulb</span>
                    <div class="text-xs text-amber-200/80">
                        <strong class="text-amber-300">Tip:</strong> In Finder, press
                        <kbd class="px-1.5 py-0.5 bg-black/30 rounded text-[10px] mx-0.5">Cmd</kbd>+<kbd class="px-1.5 py-0.5 bg-black/30 rounded text-[10px] mx-0.5">Shift</kbd>+<kbd class="px-1.5 py-0.5 bg-black/30 rounded text-[10px] mx-0.5">.</kbd>
                        to show hidden files and folders.
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="p-4 border-t border-white/5 flex justify-end">
            <button onclick="closeHiddenPathModal()" class="px-5 py-2 bg-white/5 text-gray-400 font-medium rounded-lg hover:bg-white/10 hover:text-white transition-colors">
                Close
            </button>
        </div>
    </div>
</div>

<style>
    #hiddenPathModal.active { display: flex !important; opacity: 1; }
    #hiddenPathModal.active > div { transform: scale(1); }
</style>
"""

SETUP_WIZARD_COMPONENT = """
<!-- First-Run Setup Wizard -->
<div id="setupWizard" class="hidden fixed inset-0 z-50 bg-gradient-to-br from-[#0a0a12] via-[#1a1a24] to-[#0a0a12] flex items-center justify-center p-4">
    <div class="w-full max-w-3xl">
        
        <!-- Welcome Header -->
        <div class="text-center mb-8">
            <div class="inline-block p-4 bg-arcade-cyan/10 rounded-full mb-4">
                <span class="material-icons text-6xl text-arcade-cyan">rocket_launch</span>
            </div>
            <h1 class="text-4xl font-bold text-white mb-2">Welcome to Arcade Media Scanner!</h1>
            <p class="text-gray-400 text-lg">Let's configure your media library in just a few steps</p>
        </div>

        <!-- Setup Card -->
        <div class="bg-[#1a1a24] rounded-2xl shadow-2xl border border-white/10 p-8">
            
            <!-- Step 1: Select Directories -->
            <div class="mb-8">
                <div class="flex items-center gap-3 mb-4">
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-arcade-cyan text-black font-bold text-sm">1</span>
                    <h2 class="text-xl font-semibold text-white">Select Media Directories</h2>
                </div>
                <p class="text-sm text-gray-400 mb-4">Choose which directories to scan for videos and images. Your media is mounted at <code class="px-2 py-0.5 bg-black/40 rounded text-arcade-cyan">/media</code></p>
                
                <!-- Directory List -->
                <div id="setupDirectoryList" class="space-y-2 max-h-64 overflow-y-auto">
                    <!-- Populated dynamically -->
                    <div class="flex items-center justify-center py-8 text-gray-500">
                        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-arcade-cyan mr-3"></div>
                        <span>Loading directories...</span>
                    </div>
                </div>
            </div>

            <!-- Step 2: Image Scanning -->
            <div class="mb-8 p-4 bg-black/20 rounded-lg border border-white/5">
                <div class="flex items-center gap-3 mb-3">
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-arcade-cyan text-black font-bold text-sm">2</span>
                    <h2 class="text-xl font-semibold text-white">Image Scanning</h2>
                </div>
                <label class="flex items-center gap-3 cursor-pointer select-none">
                    <div class="relative inline-flex items-center">
                        <input type="checkbox" id="setupScanImages" class="sr-only peer">
                        <div class="w-11 h-6 bg-gray-700 rounded-full peer peer-focus:ring-2 peer-focus:ring-arcade-cyan/50 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-arcade-cyan"></div>
                    </div>
                    <div>
                        <span class="text-white font-medium">Scan images (JPG, PNG, RAW, etc.)</span>
                        <p class="text-xs text-gray-500">Enable if you have photo libraries</p>
                    </div>
                </label>
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-between pt-6 border-t border-white/10">
                <button onclick="skipSetup()" class="px-6 py-2.5 text-gray-400 hover:text-white transition-colors text-sm">
                    Skip for now
                </button>
                <button onclick="completeSetup()" id="setupCompleteBtn" disabled class="px-8 py-3 bg-arcade-cyan text-black font-bold rounded-lg hover:bg-cyan-300 transition-all shadow-lg shadow-arcade-cyan/20 disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed disabled:shadow-none">
                    Complete Setup →
                </button>
            </div>
        </div>

        <!-- Help Text -->
        <div class="text-center mt-6 text-sm text-gray-500">
            You can change these settings later in <span class="text-arcade-cyan">Settings → General</span>
        </div>
    </div>
</div>

<style>
    #setupWizard.active { display: flex !important; }
    
    /* Custom scrollbar for directory list */
    #setupDirectoryList::-webkit-scrollbar {
        width: 8px;
    }
    #setupDirectoryList::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
    }
    #setupDirectoryList::-webkit-scrollbar-thumb {
        background: rgba(100, 255, 218, 0.2);
        border-radius: 4px;
    }
    #setupDirectoryList::-webkit-scrollbar-thumb:hover {
        background: rgba(100, 255, 218, 0.3);
    }
    
    .setup-dir-card {
        padding: 1rem;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 0.5rem;
        transition: all 0.2s;
        cursor: pointer;
    }
    .setup-dir-card:hover {
        background: rgba(100, 255, 218, 0.05);
        border-color: rgba(100, 255, 218, 0.3);
    }
    .setup-dir-card.selected {
        background: rgba(100, 255, 218, 0.15);
        border-color: rgba(100, 255, 218, 0.5);
    }
</style>
"""

SETTINGS_MODAL_COMPONENT = """
<div id="settingsModal" class="hidden fixed inset-0 z-40 bg-black/80 backdrop-blur-sm opacity-0 transition-opacity duration-300 flex items-center justify-center p-4 md:p-8">
    <div class="settings-container w-full h-full md:w-2/3 md:h-auto md:max-w-5xl md:max-h-[85vh] bg-arcade-bg dark:bg-[#1a1a24] rounded-2xl animate-glow-pulse glow-cyan flex flex-col md:flex-row overflow-hidden border border-black/10 dark:border-white/10 transform scale-95 transition-transform duration-300">
        
        <!-- Sidebar Navigation -->
        <aside class="w-full md:w-56 bg-[#f1f3f5] dark:bg-[#12121a] border-b md:border-b-0 md:border-r border-black/10 dark:border-white/5 flex md:flex-col shrink-0">
            <div class="p-4 md:p-5 flex items-center gap-3 border-b border-black/8 dark:border-white/5 md:border-none">
                <span class="material-icons text-arcade-gold text-xl">settings</span>
                <h2 class="font-semibold tracking-wide text-lg text-text-main dark:text-white">Settings</h2>
            </div>
            
            <nav class="flex md:flex-col overflow-x-auto md:overflow-visible p-2 md:px-3 md:py-2 gap-1">
                <button class="settings-nav-item active flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="scanning">
                    <span class="material-icons text-lg">folder_open</span>
                    <span class="hidden md:inline">Scanning</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="performance">
                    <span class="material-icons text-lg">speed</span>
                    <span class="hidden md:inline">Performance</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="interface">
                    <span class="material-icons text-lg">palette</span>
                    <span class="hidden md:inline">Interface</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                
                <div class="w-px h-6 md:w-full md:h-px bg-white/10 md:my-2 mx-2 md:mx-0"></div>
                
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="storage">
                    <span class="material-icons text-lg">storage</span>
                    <span class="hidden md:inline">Storage</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <div class="w-px h-6 md:w-full md:h-px bg-white/10 md:my-2 mx-2 md:mx-0"></div>
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="privacy">
                    <span class="material-icons text-lg">security</span>
                    <span class="hidden md:inline">Privacy</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <div class="w-px h-6 md:w-full md:h-px bg-white/10 md:my-2 mx-2 md:mx-0"></div>
                 <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="backup">
                    <span class="material-icons text-lg">save</span>
                    <span class="hidden md:inline">Backup & Restore</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <div class="w-px h-6 md:w-full md:h-px bg-white/10 md:my-2 mx-2 md:mx-0"></div>
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="queue">
                    <span class="material-icons text-lg">cloud_sync</span>
                    <span class="hidden md:inline">Remote Queue</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
            </nav>
        </aside>
        
        <!-- Main Content -->
        <main class="flex-1 flex flex-col min-w-0 bg-arcade-bg dark:bg-[#1a1a24]">
            
            <!-- Header -->
            <header class="p-5 md:p-6 border-b border-white/5 flex justify-between items-center">
                <div>
                    <h1 id="section-title" class="text-xl md:text-2xl font-bold text-white">Scanning</h1>
                    <p id="section-subtitle" class="text-sm text-gray-500 mt-0.5">Configure video library scanning</p>
                </div>
                <button class="text-gray-500 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg" title="Close (ESC)" onclick="closeSettings()">
                    <span class="material-icons">close</span>
                </button>
            </header>
            
            <!-- Scrollable Body -->
            <div class="settings-body flex-1 overflow-y-auto p-5 md:p-6 space-y-6">
                
                <!-- SCANNING SECTION -->
                <div class="content-section active space-y-6" id="content-scanning">
                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">folder</span>
                                Scan Directories
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Paths to scan for video files. One per line.</p>
                        </div>
                        <textarea class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-gray-300 font-mono focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all resize-none placeholder-gray-600" id="settingsTargets" placeholder="/Users/username/Videos" rows="4" oninput="markSettingsUnsaved()"></textarea>
                        
                        <div class="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 flex gap-3 text-sm text-blue-300">
                             <span class="material-icons text-blue-400 text-lg">info</span>
                             <div>
                                 <strong>Default:</strong> Home directory
                                 <span id="defaultTargetsHint" class="opacity-70 text-xs block mt-0.5"></span>
                             </div>
                        </div>
                    </section>
                    
                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-gray-400">block</span>
                                System Exclusions
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Default paths excluded from scanning.</p>
                        </div>
                        <div id="defaultExclusionsContainer" class="bg-black/30 rounded-xl p-4 border border-white/5 space-y-2 max-h-48 overflow-y-auto">
                            <!-- Populated by JS -->
                        </div>
                    </section>
                    
                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-pink">remove_circle</span>
                                Custom Exclusions
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Additional paths to exclude.</p>
                        </div>
                        <textarea class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-gray-300 font-mono focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all resize-none placeholder-gray-600" id="settingsExcludes" placeholder="/Volumes/Backup" rows="2" oninput="markSettingsUnsaved()"></textarea>
                    </section>

                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-gray-400">notes</span>
                                Logging
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Control terminal output density during scans.</p>
                        </div>
                        <label class="flex items-center gap-3 cursor-pointer select-none group bg-black/30 p-4 rounded-xl border border-white/5 hover:border-arcade-cyan/30 transition-all">
                            <div class="relative inline-flex items-center">
                                <input type="checkbox" id="settingsVerboseScanning" class="sr-only peer" onchange="markSettingsUnsaved()">
                                <div class="w-11 h-6 bg-gray-700 rounded-full peer peer-focus:ring-2 peer-focus:ring-arcade-cyan/50 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-arcade-cyan"></div>
                            </div>
                            <div>
                                <span class="text-white font-medium">Verbose Scanning Logs</span>
                                <p class="text-xs text-gray-500">Show individual filenames. Keep disabled for cleaner summaries.</p>
                            </div>
                        </label>
                    </section>
                </div>
                
                <!-- PERFORMANCE SECTION -->
                <div class="content-section hidden space-y-6" id="content-performance">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-gold">straighten</span>
                                File Size Threshold
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Ignore videos smaller than this size.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Minimum Size</div>
                                <div class="text-xs text-gray-500 mt-0.5">Files below this are skipped</div>
                            </div>
                            <div class="flex items-center gap-2 bg-black/50 rounded-lg border border-white/10 p-1">
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsMinSize', -10)">
                                    <span class="material-icons text-lg">remove</span>
                                </button>
                                <div class="flex items-center gap-1">
                                    <input type="number" id="settingsMinSize" value="100" min="1" class="bg-transparent text-white font-mono text-center w-14 focus:outline-none" oninput="markSettingsUnsaved()">
                                    <span class="text-gray-500 text-sm">MB</span>
                                </div>
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsMinSize', 10)">
                                    <span class="material-icons text-lg">add</span>
                                </button>
                            </div>
                        </div>
                    </section>
                    
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">image</span>
                                Image Size Threshold
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Ignore images smaller than this. Filters out tiny icons/thumbnails.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Minimum Size</div>
                                <div class="text-xs text-gray-500 mt-0.5">Images below this are skipped</div>
                            </div>
                            <div class="flex items-center gap-2 bg-black/50 rounded-lg border border-white/10 p-1">
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsMinImageSize', -50)">
                                    <span class="material-icons text-lg">remove</span>
                                </button>
                                <div class="flex items-center gap-1">
                                    <input type="number" id="settingsMinImageSize" value="100" min="0" max="5000" step="50" class="bg-transparent text-white font-mono text-center w-14 focus:outline-none" oninput="markSettingsUnsaved()">
                                    <span class="text-gray-500 text-sm">KB</span>
                                </div>
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsMinImageSize', 50)">
                                    <span class="material-icons text-lg">add</span>
                                </button>
                            </div>
                        </div>
                    </section>
                    
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-pink">local_fire_department</span>
                                Bitrate Classification
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Videos above this are marked as HIGH bitrate.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Bitrate Threshold</div>
                                <div class="text-xs text-gray-500 mt-0.5">Default: 15,000 kbps</div>
                            </div>
                            <div class="flex items-center gap-2 bg-black/50 rounded-lg border border-white/10 p-1">
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsBitrate', -1000)">
                                    <span class="material-icons text-lg">remove</span>
                                </button>
                                <div class="flex items-center gap-1">
                                    <input type="number" id="settingsBitrate" value="15000" min="1000" class="bg-transparent text-white font-mono text-center w-20 focus:outline-none" oninput="markSettingsUnsaved()">
                                    <span class="text-gray-500 text-sm">kbps</span>
                                </div>
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsBitrate', 1000)">
                                    <span class="material-icons text-lg">add</span>
                                </button>
                            </div>
                        </div>
                    </section>

                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">speed</span>
                                Thumbnail Pre-computation
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Generate thumbnails during scan to prevent lag while scrolling.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Pre-compute Thumbnails</div>
                                <div class="text-xs text-gray-500 mt-0.5">Highly recommended for NAS users.</div>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="settingsPrecomputeThumbs" class="sr-only peer" onchange="markSettingsUnsaved()">
                                <div class="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-arcade-cyan"></div>
                            </label>
                        </div>
                    </section>

                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-gold">tune</span>
                                Encoding Quality
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Trade-off between encoding speed and output file size. Best quality takes longer but shrinks files more.</p>
                        </div>

                        <div class="grid grid-cols-3 gap-2" id="encodingPresetGroup">
                            <button type="button" onclick="selectEncodingPreset('fast')" id="preset-fast"
                                data-value="fast"
                                class="encoding-preset-btn flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all cursor-pointer">
                                <span class="material-icons text-2xl text-gray-400 transition-colors">bolt</span>
                                <span class="preset-label text-sm font-medium text-gray-300 transition-colors">Fast</span>
                                <span class="text-xs text-gray-500 text-center leading-tight">Quickest · bigger files</span>
                            </button>
                            <button type="button" onclick="selectEncodingPreset('balanced')" id="preset-balanced"
                                data-value="balanced"
                                class="encoding-preset-btn flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all cursor-pointer">
                                <span class="material-icons text-2xl text-gray-400 transition-colors">balance</span>
                                <span class="preset-label text-sm font-medium text-gray-300 transition-colors">Balanced</span>
                                <span class="text-xs text-gray-500 text-center leading-tight">Default · good mix</span>
                            </button>
                            <button type="button" onclick="selectEncodingPreset('best')" id="preset-best"
                                data-value="best"
                                class="encoding-preset-btn flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all cursor-pointer">
                                <span class="material-icons text-2xl text-gray-400 transition-colors">workspace_premium</span>
                                <span class="preset-label text-sm font-medium text-gray-300 transition-colors">Best</span>
                                <span class="text-xs text-gray-500 text-center leading-tight">Smallest files · slow</span>
                            </button>
                        </div>
                        <input type="hidden" id="settingsEncodingPreset" value="balanced">
                    </section>
                </div>
                
                <!-- INTERFACE SECTION -->
                <div class="content-section hidden space-y-6" id="content-interface">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-magenta">palette</span>
                                Theme
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Customize the visual style.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 space-y-4">
                            <label class="block text-xs text-gray-400 mb-1">Color Paradigm</label>
                            <select id="settingsTheme" onchange="markSettingsUnsaved()" class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none">
                                <option value="arcade">Arcade (Neon)</option>
                                <option value="professional">Professional (Clean)</option>
                                <option value="candy">Candy (Pastel)</option>
                            </select>
                            <p class="text-xs text-gray-500">Use the header toggle (Sun/Moon) to switch between Light/Dark mode for any theme.</p>
                        </div>
                    </section>

                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-magenta">auto_awesome</span>
                                Visual Features
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Customize the dashboard experience.</p>
                        </div>
                        

                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Video Optimizer</div>
                                <div class="text-xs text-gray-500 mt-0.5">Enable video compression features <span class="text-amber-400">(restart required)</span></div>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="settingsOptimizer" class="sr-only peer" checked onchange="markSettingsUnsaved()">
                                <div class="w-12 h-7 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-arcade-cyan/30 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-6 after:w-6 after:shadow-md after:transition-all peer-checked:bg-arcade-gold"></div>
                            </label>
                        </div>

                        <!-- INCLUDE PHOTOS -->
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Include Photos</div>
                                <div class="text-xs text-gray-500 mt-0.5">Include <span class="text-arcade-cyan">.jpg, .png, .gif</span> etc. in library</div>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="settingsScanImages" class="sr-only peer" onchange="onIncludePhotosChange(this)">
                                <div class="w-12 h-7 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-arcade-cyan/30 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-6 after:w-6 after:shadow-md after:transition-all peer-checked:bg-arcade-cyan"></div>
                            </label>
                        </div>

                        <!-- REMOVE PHOTOS CONFIRMATION MODAL -->
                        <div id="removePhotosModal" class="hidden fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                            <div class="bg-[#1a1a2e] border border-white/10 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">
                                <div class="flex items-center gap-3 mb-4">
                                    <span class="material-icons text-yellow-400 text-2xl">warning</span>
                                    <h3 class="text-white font-semibold text-lg">Remove existing photos?</h3>
                                </div>
                                <p class="text-gray-400 text-sm mb-6">
                                    Do you want to <span class="text-white font-medium">remove all existing photos</span> from the library database?
                                    They won't be deleted from disk — just removed from the index.
                                </p>
                                <div class="flex gap-3">
                                    <button onclick="confirmRemovePhotos(true)" class="flex-1 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-300 rounded-xl py-2.5 text-sm font-medium transition-colors">
                                        Yes, remove from DB
                                    </button>
                                    <button onclick="confirmRemovePhotos(false)" class="flex-1 bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 rounded-xl py-2.5 text-sm font-medium transition-colors">
                                        Keep in library
                                    </button>
                                </div>
                            </div>
                        </div>


                    </section>
                </div>
                
                <!-- STORAGE SECTION -->
                <div class="content-section hidden space-y-6" id="content-storage">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">pie_chart</span>
                                Cache Statistics
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Disk space used by generated assets.</p>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-3">
                            <div class="bg-black/40 p-4 rounded-xl border border-white/5 flex flex-col items-center gap-2">
                                <span class="material-icons text-gray-500 text-2xl">image</span>
                                <span class="text-xs text-gray-500 uppercase tracking-wider">Thumbnails</span>
                                <span class="text-lg font-mono text-white" id="statThumbnails">—</span>
                            </div>
                            <div class="bg-black/40 p-4 rounded-xl border border-arcade-cyan/30 flex flex-col items-center gap-2">
                                <span class="material-icons text-arcade-cyan text-2xl">storage</span>
                                <span class="text-xs text-gray-500 uppercase tracking-wider">Total</span>
                                <span class="text-lg font-mono text-arcade-cyan" id="statTotal">—</span>
                            </div>
                        </div>
                        
                        <div class="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 flex gap-3 text-sm text-amber-200">
                            <span class="material-icons text-amber-400 text-lg">info</span>
                            <div>Cache changes require an app restart. Clearing cache deletes all thumbnails.</div>
                        </div>
                    </section>
                    </section>
                </div>

                <!-- PRIVACY SECTION -->
                <div class="content-section hidden space-y-6" id="content-privacy">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">shield</span>
                                Safe Mode Configuration
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Define what content is hidden when Safe Mode is enabled.</p>
                        </div>

                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Enable Safe Mode</div>
                                <div class="text-xs text-gray-500 mt-0.5">Hide sensitive content based on tags and directories</div>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="settingsSafeMode" class="sr-only peer" onchange="markSettingsUnsaved()">
                                <div class="w-12 h-7 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-arcade-cyan/30 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-6 after:w-6 after:shadow-md after:transition-all peer-checked:bg-green-500"></div>
                            </label>
                        </div>

                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 space-y-4">
                            <div>
                                <label class="block text-xs font-medium text-white mb-2">Sensitive Directories</label>
                                <textarea class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-gray-300 font-mono focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all resize-none placeholder-gray-600" id="settingsSensitiveDirs" placeholder="/path/to/private" rows="3" oninput="markSettingsUnsaved()"></textarea>
                                <p class="text-xs text-gray-500 mt-1">One absolute path per line. Files in these folders will be hidden.</p>
                            </div>
                            
                            <div>
                                <label class="block text-xs font-medium text-white mb-2">Sensitive Tags</label>
                                <input type="text" id="settingsSensitiveTags" placeholder="nsfw, adult" class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-arcade-cyan/50 focus:outline-none" oninput="markSettingsUnsaved()">
                                <p class="text-xs text-gray-500 mt-1">Comma separated list of tags to hide.</p>
                            </div>
                            
                            <div>
                                <label class="block text-xs font-medium text-white mb-2">Sensitive Collections</label>
                                <textarea class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-gray-300 font-mono focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all resize-none placeholder-gray-600" id="settingsSensitiveCollections" placeholder="My Private Collection" rows="3" oninput="markSettingsUnsaved()"></textarea>
                                <p class="text-xs text-gray-500 mt-1">One collection name per line. These collections will be hidden from the sidebar.</p>
                            </div>
                        </div>
                    </section>
                </div>

                <!-- BACKUP SECTION -->
                <div class="content-section hidden space-y-6" id="content-backup">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">cloud_download</span>
                                Export Settings
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Download your current configuration, including collections and tags.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Backup Configuration</div>
                                <div class="text-xs text-gray-500 mt-0.5">Saves as arcade_settings_backup.json</div>
                            </div>
                            <button onclick="exportSettings()" class="px-4 py-2 bg-white/5 hover:bg-white/10 text-white rounded-lg text-sm font-medium transition-colors border border-white/10 flex items-center gap-2">
                                <span class="material-icons text-sm">download</span>
                                Download
                            </button>
                        </div>
                    </section>

                    <section class="space-y-4">
                         <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-pink">cloud_upload</span>
                                Import Settings
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Restore configuration from a backup file. Existing settings will be overwritten.</p>
                        </div>
                        
                         <div class="bg-black/30 rounded-xl p-4 border border-white/5 space-y-4">
                            <div class="flex items-center gap-4">
                                <div class="flex-1">
                                    <label class="block text-sm font-medium text-white mb-1">Select Backup File</label>
                                    <input type="file" id="settingsImportFile" accept=".json" class="block w-full text-xs text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-white/10 file:text-white hover:file:bg-white/20 cursor-pointer">
                                </div>
                                <button onclick="importSettings()" class="px-4 py-2 bg-arcade-cyan/20 hover:bg-arcade-cyan/30 text-arcade-cyan rounded-lg text-sm font-medium transition-colors border border-arcade-cyan/30 flex items-center gap-2 h-[38px] mt-6">
                                    <span class="material-icons text-sm">upload</span>
                                    Restore
                                </button>
                            </div>
                             <div class="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 flex gap-3 text-sm text-yellow-200">
                                <span class="material-icons text-yellow-400 text-lg">warning</span>
                                <div>Restoring will reload the page and apply settings immediately.</div>
                            </div>
                         </div>
                    </section>
                </div>

                <!-- REMOTE QUEUE SECTION -->
                <div class="content-section hidden space-y-6" id="content-queue">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">cloud_sync</span>
                                Encoding Queue
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Files queued for remote Mac encoding. The Mac worker polls for pending jobs.</p>
                        </div>

                        <div class="bg-black/30 rounded-xl border border-white/5 overflow-hidden">
                            <table class="w-full text-sm">
                                <thead>
                                    <tr class="border-b border-white/5 text-gray-500 text-xs uppercase tracking-wider">
                                        <th class="text-left px-4 py-3">Status</th>
                                        <th class="text-left px-4 py-3">File</th>
                                        <th class="text-left px-4 py-3 hidden md:table-cell">Queued</th>
                                        <th class="text-left px-4 py-3 hidden md:table-cell">Result</th>
                                        <th class="text-right px-4 py-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="queueTableBody">
                                    <tr><td colspan="5" class="px-4 py-8 text-center text-gray-600">No jobs yet</td></tr>
                                </tbody>
                            </table>
                        </div>

                        <div class="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 flex gap-3 text-sm text-blue-300">
                            <span class="material-icons text-blue-400 text-lg">info</span>
                            <div>Start the Mac worker with: <code class="px-2 py-0.5 bg-black/40 rounded text-arcade-cyan">python3 mac_worker.py --server http://&lt;ip&gt;:8000 --user admin</code></div>
                        </div>
                    </section>
                </div>
            </div>
            
            <!-- Footer -->
            <footer class="p-4 border-t border-black/8 dark:border-white/5 bg-[#f1f3f5] dark:bg-[#12121a] flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <div class="flex items-center gap-2 text-amber-400 text-xs font-medium opacity-0 transition-opacity" id="unsavedIndicator">
                        <span class="material-icons text-sm">warning</span>
                        Unsaved changes
                    </div>
                </div>
                <div class="flex gap-3">
                    <button class="px-4 py-2 rounded-lg text-sm font-medium text-text-muted dark:text-gray-400 hover:text-text-main dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-all" onclick="closeSettings()">Cancel</button>
                    <button id="saveSettingsBtn" class="px-5 py-2 rounded-lg text-sm font-bold text-black bg-arcade-cyan hover:bg-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-arcade-cyan/20 transition-all flex items-center gap-2" onclick="saveSettings()">
                        <span class="material-icons text-lg save-icon">save</span>
                        <svg class="animate-spin h-4 w-4 save-spinner hidden" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span class="save-text">Save</span>
                    </button>
                </div>
            </footer>
            
        </main>
    </div>
</div>

<!-- Settings Toast Notification -->
<div id="settingsToast" class="fixed bottom-6 right-6 z-50 transform translate-y-20 opacity-0 transition-all duration-300 pointer-events-none">
    <div class="bg-green-500/95 backdrop-blur text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3">
        <span class="material-icons">check_circle</span>
        <span class="font-medium">Settings saved</span>
    </div>
</div>
"""


FILTER_BAR_COMPONENT = """
<!-- Filter Bar (Simplified with Unified Filter Panel) -->
<div class="workspace-indicator sticky top-[34px] md:top-16 z-30 bg-arcade-bg/95 backdrop-blur border-b-2 px-2 md:px-6 py-2 flex flex-col md:flex-row gap-3 md:items-center justify-between transition-all duration-300 overflow-x-hidden" style="border-color: var(--ws-accent, var(--cyan)); background: var(--ws-bg-tint, transparent);">
    <!-- Search Input -->
    <div class="w-full md:w-80 lg:w-96 relative flex-shrink min-w-0">
        <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 text-[18px]">search</span>
        <input type="text" id="mobileSearchInput" oninput="onSearchInput()" placeholder="Search..." class="w-full bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 rounded-full pl-10 pr-4 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:border-arcade-cyan/50 focus:bg-black/10 dark:focus:bg-white/10 transition-all placeholder-gray-500 dark:placeholder-gray-600">
    </div>
    
    <!-- Filter Controls (Simplified) -->
    <div class="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 scrollbar-hide flex-shrink-0">
        <!-- Unified Filters Button -->
        <button id="openFiltersBtn" onclick="openFilterPanel()" class="flex items-center gap-2 bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 rounded-full px-4 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-black/10 dark:hover:bg-white/10 hover:text-black dark:hover:text-white hover:border-arcade-cyan/50 transition-all">
            <span class="material-icons text-[16px]">tune</span>
            <span>Filters</span>
            <span id="filterBadge" class="hidden bg-arcade-cyan text-black text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">0</span>
        </button>
        
        <!-- Sort Dropdown (kept for quick access) -->
        <div class="relative group">
            <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-[16px] pointer-events-none group-hover:text-arcade-cyan transition-colors">sort</span>
            <select id="sortSelect" onchange="setSort(this.value)" class="bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 rounded-full pl-9 pr-4 py-1.5 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:border-arcade-cyan/50 appearance-none min-w-[140px] cursor-pointer hover:bg-black/10 dark:hover:bg-white/10 transition-colors">
                <option value="bitrate">Bitrate ↓</option>
                <option value="size">Size ↓</option>
                <option value="runtime">Runtime ↓</option>
                <option value="date">Date ↓</option>
            </select>
        </div>
        
        <!-- View Toggles & Grid Scale -->
        <div class="hidden md:flex items-center bg-black/5 dark:bg-white/5 rounded-lg p-0.5 ml-2 border border-black/5 dark:border-white/5">
            <!-- Grid Scale Slider -->
            <div class="flex items-center gap-1.5 px-2 mr-1 border-r border-black/10 dark:border-white/10 group" id="gridScaleContainer">
                <span class="material-icons text-[14px] text-gray-500/70 group-hover:text-arcade-cyan transition-colors">photo_size_select_small</span>
                <input type="range" id="gridScaleSlider" min="150" max="500" value="240" step="10" oninput="updateGridScale(this.value)" class="w-16 h-1 bg-black/10 dark:bg-white/10 rounded-full appearance-none cursor-pointer">
                <span class="material-icons text-[16px] text-gray-500/70 group-hover:text-arcade-cyan transition-colors">photo_size_select_large</span>
            </div>
            
            <button id="viewToggleGrid" onclick="setLayout('grid')" class="p-1.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white transition-colors" title="Grid View">
                <span class="material-icons text-[18px]">grid_view</span>
            </button>
            <button id="viewToggleList" onclick="setLayout('list')" class="p-1.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white transition-colors" title="List View">
                 <span class="material-icons text-[18px]">view_list</span>
            </button>
            <button id="viewToggleTreemap" onclick="setLayout('treemap')" class="p-1.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white transition-colors" title="Tree View">
                <span class="material-icons text-[18px]">account_tree</span>
            </button>
            <button id="viewToggleFolder" onclick="setLayout('folderbrowser')" class="p-1.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white transition-colors" title="Folder Browser">
                <span class="material-icons text-[18px]">folder</span>
            </button>
        </div>
        
        <button id="refreshBtn" onclick="rescanLibrary()" class="bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white p-2 rounded-full transition-colors flex items-center justify-center flex-shrink-0" title="Rescan Library">
            <span class="material-icons text-[18px]">refresh</span>
        </button>
    </div>
</div>

<!-- Active Filters Row (shows when filters are active) -->
<div id="activeFiltersRow" class="hidden sticky top-[82px] md:top-[80px] z-20 bg-arcade-bg/90 backdrop-blur px-2 md:px-6 py-2 border-b border-black/5 dark:border-white/5 flex flex-wrap items-center gap-2">
    <span class="text-xs text-gray-500 font-medium">Active:</span>
    <div id="activeFilterChips" class="flex flex-wrap gap-1.5">
        <!-- Chips injected by JS -->
    </div>
    <button onclick="resetFilters()" class="ml-auto text-xs text-gray-500 hover:text-arcade-pink transition-colors">Clear all</button>
</div>
"""

LIST_VIEW_COMPONENT = """
<!-- List View Template (Hidden by default) -->
<div id="listViewContainer" class="hidden w-full overflow-x-auto">
    <table class="w-full text-left border-collapse">
        <thead>
            <tr class="text-xs text-gray-500 border-b border-white/10">
                <th class="p-3 font-medium">File</th>
                <th class="p-3 font-medium">Size</th>
                <th class="p-3 font-medium hidden md:table-cell">Duration</th>
                <th class="p-3 font-medium hidden md:table-cell">Codec</th>
                <th class="p-3 font-medium text-right">Action</th>
            </tr>
        </thead>
        <tbody id="listTableBody" class="text-sm text-gray-300">
            <!-- Rows injected by JS -->
        </tbody>
    </table>
</div>
"""

