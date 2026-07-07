const fs = require('fs');
const path = require('path');

const credPath = path.join(__dirname, 'src', 'views', 'credentials.json');

if (!fs.existsSync(credPath)) {
	fs.writeFileSync(credPath, JSON.stringify({username: '', password: ''}, null, 2));
	console.log('✅ Created dummy credentials.json');
} else {
	console.log('✅ credentials.json already exists');
}
