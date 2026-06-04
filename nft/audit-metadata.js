#!/usr/bin/env node

/**
 * audit-metadata.js — Read-only metadata audit for all 251 Holy Chip NFTs.
 *
 * For each NFT:
 *   1. Fetch on-chain URI via Metaplex SDK
 *   2. HTTP-fetch that URI
 *   3. Check: valid JSON + has `image` field + has a `Character` attribute
 *
 * Reports OK vs broken, lists all broken ones with reason.
 * NO on-chain writes.
 */

const { Metaplex, keypairIdentity } = require('@metaplex-foundation/js');
const { Connection, Keypair, PublicKey } = require('@solana/web3.js');
const fs = require('fs');
const https = require('https');
const http = require('http');

// Read-only: we still need a keypair for Metaplex SDK init, but we never sign anything
const RPC = 'https://api.mainnet-beta.solana.com';
const connection = new Connection(RPC, 'confirmed');

// Load hot wallet just to initialise Metaplex (read-only operations don't need signing)
const keypair = Keypair.fromSecretKey(
  Uint8Array.from(JSON.parse(fs.readFileSync(process.env.HOME + '/holy-chip-wallet.json')))
);
const metaplex = Metaplex.make(connection).use(keypairIdentity(keypair));

// ── helpers ──────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/** Fetch a URL and return the response body as a string (follows redirects). */
function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith('https') ? https : http;
    const req = lib.get(url, { timeout: 15000 }, (res) => {
      // Handle redirects
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        fetchUrl(res.headers.location).then(resolve).catch(reject);
        return;
      }
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timed out')); });
  });
}

/** Check a single URI: returns { ok, reasons } */
async function checkUri(uri) {
  const reasons = [];
  let body;

  try {
    body = await fetchUrl(uri);
  } catch (err) {
    return { ok: false, reasons: [`URI fetch failed: ${err.message}`] };
  }

  let json;
  try {
    json = JSON.parse(body);
  } catch {
    return { ok: false, reasons: [`Response is not valid JSON (got: ${body.slice(0, 80)})`] };
  }

  if (!json.image) {
    reasons.push('Missing `image` field');
  }

  const attrs = json.attributes || [];
  const hasCharacter = attrs.some(a => a.trait_type === 'Character' && a.value);
  if (!hasCharacter) {
    reasons.push('Missing `Character` attribute');
  }

  return { ok: reasons.length === 0, reasons, name: json.name };
}

// ── fetch on-chain URI for one mint ─────────────────────────────────────────

async function getOnChainUri(mintAddress) {
  const nft = await metaplex.nfts().findByMint({ mintAddress: new PublicKey(mintAddress) });
  return { uri: nft.uri, name: nft.name };
}

// ── main ─────────────────────────────────────────────────────────────────────

async function main() {
  const allMints = JSON.parse(fs.readFileSync('all-mints.json', 'utf8'));
  const total = allMints.length;
  console.log(`\nAuditing ${total} Holy Chip NFTs (read-only)\n`);
  console.log('Step 1: Fetching on-chain URIs (batches of 5, 1s delay between batches)...\n');

  // ── Phase 1: fetch all on-chain URIs ──────────────────────────────────────
  const BATCH_SIZE = 5;
  const RPC_DELAY = 1200; // ms between batches

  const onChainData = []; // { mintAddress, name, uri, error }

  for (let i = 0; i < total; i += BATCH_SIZE) {
    const batch = allMints.slice(i, i + BATCH_SIZE);
    const results = await Promise.allSettled(
      batch.map(m => getOnChainUri(m.mintAddress))
    );

    results.forEach((res, idx) => {
      const mint = batch[idx];
      if (res.status === 'fulfilled') {
        onChainData.push({
          mintAddress: mint.mintAddress,
          originalName: mint.name,
          onChainName: res.value.name,
          uri: res.value.uri,
        });
      } else {
        onChainData.push({
          mintAddress: mint.mintAddress,
          originalName: mint.name,
          onChainName: null,
          uri: null,
          rpcError: res.reason?.message || String(res.reason),
        });
      }
    });

    const done = Math.min(i + BATCH_SIZE, total);
    process.stdout.write(`  Fetched URIs: ${done}/${total}\r`);

    if (i + BATCH_SIZE < total) {
      await sleep(RPC_DELAY);
    }
  }

  console.log(`\n  Done fetching on-chain URIs.\n`);

  // ── Phase 2: HTTP-fetch all URIs in parallel batches ──────────────────────
  console.log('Step 2: Fetching and checking metadata JSON (batches of 20 concurrent)...\n');

  const HTTP_BATCH = 20;
  const HTTP_DELAY = 300;

  const auditResults = []; // { mintAddress, name, uri, ok, reasons }

  for (let i = 0; i < onChainData.length; i += HTTP_BATCH) {
    const batch = onChainData.slice(i, i + HTTP_BATCH);
    const results = await Promise.allSettled(
      batch.map(item => {
        if (item.rpcError) {
          return Promise.resolve({ ok: false, reasons: [`RPC error: ${item.rpcError}`] });
        }
        if (!item.uri) {
          return Promise.resolve({ ok: false, reasons: ['No URI on-chain'] });
        }
        return checkUri(item.uri);
      })
    );

    results.forEach((res, idx) => {
      const item = batch[idx];
      const check = res.status === 'fulfilled'
        ? res.value
        : { ok: false, reasons: [`Unexpected error: ${res.reason}`] };

      auditResults.push({
        mintAddress: item.mintAddress,
        originalName: item.originalName,
        onChainName: item.onChainName,
        uri: item.uri,
        ok: check.ok,
        reasons: check.reasons,
      });
    });

    const done = Math.min(i + HTTP_BATCH, total);
    process.stdout.write(`  Checked metadata: ${done}/${total}\r`);

    if (i + HTTP_BATCH < onChainData.length) {
      await sleep(HTTP_DELAY);
    }
  }

  console.log(`\n  Done checking metadata.\n`);

  // ── Phase 3: Report ───────────────────────────────────────────────────────
  const ok = auditResults.filter(r => r.ok);
  const broken = auditResults.filter(r => !r.ok);

  // Sort broken by original name for readability
  broken.sort((a, b) => (a.originalName || '').localeCompare(b.originalName || ''));

  console.log('═══════════════════════════════════════════════════════════════');
  console.log(' HOLY CHIP NFT METADATA AUDIT RESULTS');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`  Total checked : ${total}`);
  console.log(`  OK            : ${ok.length}`);
  console.log(`  BROKEN        : ${broken.length}`);
  console.log('═══════════════════════════════════════════════════════════════\n');

  if (broken.length === 0) {
    console.log('All NFTs have valid metadata. Nothing to fix.');
  } else {
    console.log(`BROKEN NFTs (${broken.length}):\n`);
    broken.forEach((item, i) => {
      console.log(`  ${String(i + 1).padStart(3, ' ')}. ${item.onChainName || item.originalName}`);
      console.log(`       Mint    : ${item.mintAddress}`);
      console.log(`       URI     : ${item.uri || '(none)'}`);
      console.log(`       Problem : ${item.reasons.join('; ')}`);
      console.log();
    });
  }

  // Write a machine-readable report
  const report = {
    timestamp: new Date().toISOString(),
    total,
    ok: ok.length,
    broken: broken.length,
    brokenList: broken.map(item => ({
      mintAddress: item.mintAddress,
      originalName: item.originalName,
      onChainName: item.onChainName,
      uri: item.uri,
      reasons: item.reasons,
    })),
  };
  fs.writeFileSync('audit-report.json', JSON.stringify(report, null, 2));
  console.log('Full report saved to: audit-report.json\n');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
