import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Read the actual index.js to extract the hardcoded key
const src = fs.readFileSync(path.join(__dirname, 'index.js'), 'utf8');
const match = src.match(/const apiKey\s*=\s*args\.key\s*\|\|\s*process\.env\.GEMINI_API_KEY\s*\|\|\s*"([^"]+)"/);
if (match) {
  console.log("Fallback key found, length:", match[1].length);
  console.log("Starts with AIza:", match[1].startsWith("AIza"));
} else {
  console.log("Could not extract fallback key from index.js");
  // Try another pattern
  const match2 = src.match(/apiKey[^|]*\|\|[^|]*\|\|\s*"([^"]+)"/);
  if (match2) {
    console.log("Alt match found, length:", match2[1].length);
  }
}
