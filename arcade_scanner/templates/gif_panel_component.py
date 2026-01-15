GIF_EXPORT_PANEL_COMPONENT = """
<!-- GIF Export Panel (Tailwind) -->
<div id="gifExportPanel" class="fixed bottom-0 left-0 right-0 bg-[#101018]/95 backdrop-blur-xl border-t border-white/10 p-6 translate-y-[110%] transition-transform duration-300 z-[10100] shadow-[0_-10px_40px_rgba(0,0,0,0.5)] flex flex-col gap-4">
    <!-- Active state class 'translate-y-0' handled by JS -->
    
    <!-- Preset Row -->
    <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 font-bold uppercase tracking-widest w-[60px]">Preset</div>
        <div class="flex bg-white/5 rounded-lg p-0.5 gap-0.5">
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPreset360p" onclick="setGifPreset('360p')">360p</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPreset480p" onclick="setGifPreset('480p')">480p</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="gifPreset720p" onclick="setGifPreset('720p')">720p</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPreset1080p" onclick="setGifPreset('1080p')">1080p</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifPresetOriginal" onclick="setGifPreset('original')">Original</div>
        </div>
        <div class="flex-1"></div>
        <span class="text-xs text-gray-500" id="gifPresetDesc">1280×720 - High Quality</span>
    </div>

    <!-- FPS Row -->
    <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 font-bold uppercase tracking-widest w-[60px]">FPS</div>
        <div class="flex bg-white/5 rounded-lg p-0.5 gap-0.5">
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps10" onclick="setGifFps(10)">10</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="gifFps15" onclick="setGifFps(15)">15</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps20" onclick="setGifFps(20)">20</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps25" onclick="setGifFps(25)">25</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="gifFps30" onclick="setGifFps(30)">30</div>
        </div>
        <div class="flex-1"></div>
        <span class="text-xs text-gray-500">Frame rate (higher = smoother)</span>
    </div>
    
    <!-- Trim Row -->
    <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 font-bold uppercase tracking-widest w-[60px]">Trim</div>
        <input type="text" class="bg-black/30 border border-white/10 text-white px-3 py-1.5 rounded-md font-mono text-center w-[100px] focus:border-arcade-cyan/50 focus:outline-none" id="gifTrimStart" placeholder="00:00:00" oninput="updateGifEstimate()">
        
        <button class="w-[30px] h-[30px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition-colors" onclick="setGifTrimFromHead('start')" title="Set Start">
            <span class="material-icons text-[16px]">arrow_downward</span>
        </button>
        
        <div class="w-[10px] text-center text-gray-600">-</div>
        
        <input type="text" class="bg-black/30 border border-white/10 text-white px-3 py-1.5 rounded-md font-mono text-center w-[100px] focus:border-arcade-cyan/50 focus:outline-none" id="gifTrimEnd" placeholder="END" oninput="updateGifEstimate()">
        
        <button class="w-[30px] h-[30px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition-colors" onclick="setGifTrimFromHead('end')" title="Set End">
            <span class="material-icons text-[16px]">arrow_downward</span>
        </button>
        
        <button class="w-[30px] h-[30px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition-colors ml-2" onclick="clearGifTrim()" title="Clear">
            <span class="material-icons text-[16px]">close</span>
        </button>
        
        <div class="flex-1"></div>
        <span class="text-xs text-gray-500">Duration: <span id="gifDuration" class="text-arcade-cyan">0.0s</span></span>
    </div>
    
    <!-- Quality Row -->
    <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 font-bold uppercase tracking-widest w-[60px]">Quality</div>
        <input type="number" class="bg-black/30 border border-white/10 text-white px-3 py-1.5 rounded-md font-mono text-center w-[100px] focus:border-arcade-cyan/50 focus:outline-none" id="gifQuality" placeholder="80" value="80" min="50" max="100" step="10" oninput="updateGifEstimate()">
        
        <span class="text-xs text-gray-500 font-mono">Estimated: <span id="gifEstimatedSize" class="text-arcade-cyan">~0 MB</span></span>
    </div>
    
    <!-- Actions -->
    <div class="flex items-center gap-4 mt-2">
        <button class="flex-1 py-2.5 rounded-lg font-bold cursor-pointer text-gray-400 bg-white/5 hover:bg-white/10 hover:text-white transition-all max-w-[120px]" onclick="closeGifExport()">Cancel</button>
        
        <button class="flex-1 py-2.5 rounded-lg font-bold cursor-pointer text-white bg-purple-500/20 text-purple-400 border border-purple-500/50 shadow-[0_0_15px_rgba(168,85,247,0.2)] hover:bg-purple-500 hover:text-white transition-all flex items-center justify-center gap-2" onclick="triggerGifExport()">
            <span class="material-icons">gif</span> EXPORT GIF
        </button>
    </div>
</div>
"""
