const fs = require('fs');
const path = require('path');

function w(rel, code) {
  const full = path.join(process.cwd(), rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, code, 'utf8');
  console.log('Created ' + rel);
}

