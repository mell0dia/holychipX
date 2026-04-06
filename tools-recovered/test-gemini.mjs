import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ai = new GoogleGenAI({ apiKey: "AIzaSyC0Pb1-TfjpT9sbpgkpYNIOVZLtrT4phCg" });

// Test 1: text only
console.log("Test 1: text only...");
try {
  const r = await ai.models.generateContent({
    model: "gemini-2.0-flash",
    contents: [{ role: "user", parts: [{ text: "Say hello in 5 words" }] }],
  });
  console.log("  OK:", r.candidates[0].content.parts[0].text);
} catch(e) {
  console.error("  Error:", e.message);
}

// Test 2: text + image
console.log("Test 2: text + image...");
try {
  const imgPath = path.join(__dirname, "assets", "reference.png");
  const data = fs.readFileSync(imgPath).toString("base64");
  const r = await ai.models.generateContent({
    model: "gemini-2.0-flash",
    contents: [{ role: "user", parts: [
      { inlineData: { mimeType: "image/png", data } },
      { text: "Describe this image in 10 words" }
    ] }],
  });
  console.log("  OK:", r.candidates[0].content.parts[0].text);
} catch(e) {
  console.error("  Error:", e.message);
}

// Test 3: image generation
console.log("Test 3: image generation with gemini-2.0-flash-exp-image-generation...");
try {
  const r = await ai.models.generateContent({
    model: "gemini-2.0-flash-exp-image-generation",
    contents: [{ role: "user", parts: [{ text: "Generate a simple pixel art smiley face" }] }],
    config: { responseModalities: ["Text", "Image"] },
  });
  const parts = r.candidates?.[0]?.content?.parts || [];
  for (const p of parts) {
    if (p.inlineData) {
      console.log("  OK: got image data, size:", p.inlineData.data.length, "chars");
    } else if (p.text) {
      console.log("  Text:", p.text.substring(0, 100));
    }
  }
} catch(e) {
  console.error("  Error:", e.message);
}
