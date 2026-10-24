// tests/card_meta_harness.js
// Führt cardMetaLine() aus formatters.js aus.
// Aufruf: node card_meta_harness.js <fixtures.json>
const fs = require('fs');
const path = require('path');

const { cardMetaLine } = require(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'formatters.js')
);

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(fixtures.map(cardMetaLine)));
