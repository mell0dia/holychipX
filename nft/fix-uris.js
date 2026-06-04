#!/usr/bin/env node

/**
 * Fix on-chain URIs for all Holy Chip NFTs.
 * Replace arweave.net with gateway.irys.xyz (data is on Irys, arweave.net returns 404).
 * This is a URI-only update — no metadata re-upload needed.
 * Cost: ~0.000005 SOL per tx × 251 = ~0.001 SOL total.
 */

const { Metaplex, keypairIdentity } = require('@metaplex-foundation/js');
const { Connection, Keypair, PublicKey } = require('@solana/web3.js');
const fs = require('fs');

const RPC = 'https://api.mainnet-beta.solana.com';
const connection = new Connection(RPC, 'confirmed');
const keypair = Keypair.fromSecretKey(
  Uint8Array.from(JSON.parse(fs.readFileSync(process.env.HOME + '/holy-chip-wallet.json')))
);

const metaplex = Metaplex.make(connection).use(keypairIdentity(keypair));

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const allMints = JSON.parse(fs.readFileSync('all-mints.json', 'utf8'));
  console.log(`Checking ${allMints.length} NFTs for URI fixes...\n`);

  let updated = 0;
  let skipped = 0;
  let failed = 0;

  for (let i = 0; i < allMints.length; i++) {
    const mint = allMints[i];
    const mintAddress = new PublicKey(mint.mintAddress);

    try {
      const nft = await metaplex.nfts().findByMint({ mintAddress });
      const oldUri = nft.uri;

      // Only fix URIs that use arweave.net
      if (!oldUri.includes('arweave.net')) {
        skipped++;
        console.log(`[${i + 1}/${allMints.length}] SKIP ${nft.name} — already correct`);
        continue;
      }

      const newUri = oldUri.replace('arweave.net', 'gateway.irys.xyz');

      // Verify the new URI actually works
      if (i === 0) {
        const check = await fetch(newUri);
        if (!check.ok) {
          console.error(`New URI returns ${check.status} — aborting!`);
          process.exit(1);
        }
        console.log('First URI verified OK on gateway.irys.xyz');
      }

      await metaplex.nfts().update({
        nftOrSft: nft,
        uri: newUri
      });

      updated++;
      console.log(`[${i + 1}/${allMints.length}] OK ${nft.name}: ${oldUri} -> ${newUri}`);

    } catch (err) {
      failed++;
      console.error(`[${i + 1}/${allMints.length}] FAILED ${mint.name}: ${err.message}`);
    }

    // Rate limit — 1.5s between transactions
    if (i < allMints.length - 1) {
      await sleep(1500);
    }
  }

  console.log(`\n--- DONE ---`);
  console.log(`Updated: ${updated}`);
  console.log(`Skipped: ${skipped}`);
  console.log(`Failed: ${failed}`);
}

main().catch(console.error);
