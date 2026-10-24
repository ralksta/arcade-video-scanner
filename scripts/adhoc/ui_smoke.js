const fs = require('fs');

// We simulate engine.js
const data = [{"FilePath": "/Users/ralfo/Downloads/movie.mp4", "Status": "new", "Duration_Sec": 100, "Size_MB": 100, "tags": [], "imported_at": 1000, "Bitrate_Mbps": 1.0, "codec": "h264", "hidden": false, "favorite": false, "media_type": "video"}];

function createVideoCard(v) {
    const isHevc = v.codec && (v.codec.includes('hevc') || v.codec.includes('h265'));
    const fileName = v.FilePath.split(/[\\/]/).pop();
    const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
    const dirName = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx).split(/[\\/]/).pop() : '';
    const barW = Math.min((v.Duration_Sec || 0) / 10, 100);
    
    // Check for errors!
    v.Size_MB.toFixed(0);
    v.Bitrate_Mbps.toFixed(1);
    
    return "done";
}

try {
    data.forEach(createVideoCard);
    console.log("Success");
} catch(e) {
    console.error(e);
}
