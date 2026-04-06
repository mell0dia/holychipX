// Check the API key for non-ASCII characters
const apiKey = process.env.GEMINI_API_KEY || "";
console.log("API key length:", apiKey.length);
console.log("API key type:", typeof apiKey);

for (let i = 0; i < apiKey.length; i++) {
  const code = apiKey.charCodeAt(i);
  if (code > 127) {
    console.log(`NON-ASCII at index ${i}: charCode=${code} (U+${code.toString(16).toUpperCase().padStart(4, '0')}) char=${JSON.stringify(apiKey[i])}`);
  }
}

// Check around index 128
if (apiKey.length > 125) {
  console.log("Chars around index 128:");
  for (let i = Math.max(0, 125); i < Math.min(apiKey.length, 132); i++) {
    console.log(`  [${i}] charCode=${apiKey.charCodeAt(i)} ${JSON.stringify(apiKey[i])}`);
  }
}

// Also check if there's a GEMINI_API_KEY in env with trailing whitespace
console.log("Key ends with whitespace:", /\s$/.test(apiKey));
console.log("Key starts with whitespace:", /^\s/.test(apiKey));
console.log("First 10 chars:", JSON.stringify(apiKey.slice(0, 10)));
console.log("Last 10 chars:", JSON.stringify(apiKey.slice(-10)));
