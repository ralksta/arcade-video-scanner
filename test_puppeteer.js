const http = require('http');

http.get('http://localhost:8000/api/videos', (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    try {
      const videos = JSON.parse(data);
      console.log('Got videos:', videos.length);
      console.log('First video:', videos[0] ? Object.keys(videos[0]) : 'None');
    } catch(e) {
      console.error(e);
      console.log(data.substring(0, 500));
    }
  });
}).on("error", (err) => {
  console.log("Error: " + err.message);
});
