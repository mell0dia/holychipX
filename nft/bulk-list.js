#!/usr/bin/env node

/**
 * Bulk List Holy Chip NFTs on Magic Eden at 0.3 SOL each.
 * Uses Magic Eden v2 API to get sell instructions, signs locally with keypair.
 */

const { Connection, Keypair, Transaction, VersionedTransaction } = require('@solana/web3.js');
const fs = require('fs');

const PRICE_SOL = 0.3;
const RPC = 'https://api.mainnet-beta.solana.com';
const ME_API = 'https://api-mainnet.magiceden.dev/v2';
const BATCH_DELAY_MS = 2000; // delay between listings to avoid rate limits

const keypair = Keypair.fromSecretKey(
  Uint8Array.from(JSON.parse(fs.readFileSync(process.env.HOME + '/holy-chip-wallet.json')))
);
const connection = new Connection(RPC, 'confirmed');
const wallet = keypair.publicKey.toBase58();

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function getUnlistedMints() {
  const allMints = [];
  let offset = 0;
  while (true) {
    const res = await fetch(`${ME_API}/wallets/${wallet}/tokens?offset=${offset}&limit=500&listStatus=unlisted`);
    const tokens = await res.json();
    const holyChip = tokens.filter(t => t.collection === 'holy_chip');
    allMints.push(...holyChip.map(t => t.mintAddress));
    if (tokens.length < 500) break;
    offset += 500;
  }
  return allMints;
}

async function listNFT(mintAddress) {
  const url = `${ME_API}/instructions/sell?seller=${wallet}&auctionHouseAddress=&tokenMint=${mintAddress}&tokenAccount=&price=${PRICE_SOL}&expiry=-1`;
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`ME API error: ${res.status} - ${text}`);
  }
  const data = await res.json();

  // Decode and sign the transaction
  const txBuf = Buffer.from(data.txSigned ? data.txSigned : data.tx, 'base64');

  let tx;
  try {
    // Try versioned transaction first
    tx = VersionedTransaction.deserialize(txBuf);
    tx.sign([keypair]);
    const sig = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: false });
    return sig;
  } catch (e) {
    // Fall back to legacy transaction
    tx = Transaction.from(txBuf);
    tx.partialSign(keypair);
    const sig = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: false });
    return sig;
  }
}

async function main() {
  console.log(`Wallet: ${wallet}`);
  console.log(`Price: ${PRICE_SOL} SOL per NFT\n`);

  const mints = await getUnlistedMints();
  console.log(`Found ${mints.length} unlisted Holy Chip NFTs\n`);

  if (mints.length === 0) {
    console.log('All NFTs are already listed!');
    return;
  }

  let success = 0;
  let failed = 0;

  for (let i = 0; i < mints.length; i++) {
    const mint = mints[i];
    try {
      const sig = await listNFT(mint);
      success++;
      console.log(`[${i + 1}/${mints.length}] Listed ${mint} - tx: ${sig}`);
    } catch (err) {
      failed++;
      console.error(`[${i + 1}/${mints.length}] FAILED ${mint}: ${err.message}`);
    }
    // Delay to avoid rate limits
    if (i < mints.length - 1) {
      await sleep(BATCH_DELAY_MS);
    }
  }

  console.log(`\n--- DONE ---`);
  console.log(`Listed: ${success}`);
  console.log(`Failed: ${failed}`);
  console.log(`Total: ${mints.length}`);
}

main().catch(console.error);
