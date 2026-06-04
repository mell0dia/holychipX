#!/usr/bin/env node

/**
 * Fix 108 broken Holy Chip NFTs — metadata lost during rename.
 * Rebuilds correct metadata from all-mints.json (backup) and re-uploads.
 * Cost: ~0.15 SOL (108 × ~0.0014 SOL per upload+update)
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

// Character name translations (same as rename-nfts.js)
const TRANSLATIONS = {
  'ASTRONAUTA': 'Astronaut',
  'BABY': 'Baby',
  'BOT1': 'Bot 1',
  'BOT2': 'Bot 2',
  'BUDA-MONGE-V1': 'Buddha Monk',
  'CICLOPE': 'Cyclops',
  'CONTADOR': 'Accountant',
  'ESPIROCADO': 'Spiky',
  'EYES-OF-LOVE': 'Eyes of Love',
  'IRMAO-DO-PIRATA': 'Pirate Brother',
  'JASON': 'Jason',
  'JASON-MAD': 'Mad Jason',
  'MACACO-SPACE': 'Space Monkey',
  'MACHINE': 'Machine',
  'MADMAX': 'Mad Max',
  'MEDICO-V1': 'Doctor',
  'PIRATA': 'Pirate',
  'POLICE-V1': 'Police',
  'ROBOT': 'Robot',
  'TRUMP': 'Trump',
  'VISION': 'Vision',
  'ZURETA': 'Crazy',
  '_TRUMP-MULTIVERSO': 'Trump Multiverse',
  'APOCALYPTIC': 'Apocalyptic'
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  // Load broken list from audit
  const audit = JSON.parse(fs.readFileSync('audit-report.json', 'utf8'));
  const brokenMints = new Set(audit.brokenList.map(b => b.mintAddress));

  // Load all-mints.json (ground truth backup)
  const allMints = JSON.parse(fs.readFileSync('all-mints.json', 'utf8'));

  // Build lookup: mintAddress -> original data
  const mintData = {};
  for (const m of allMints) {
    mintData[m.mintAddress] = m;
  }

  // Filter to only broken ones
  const toFix = audit.brokenList.filter(b => mintData[b.mintAddress]);
  console.log(`Fixing ${toFix.length} broken NFTs...\n`);

  let success = 0;
  let failed = 0;

  for (let i = 0; i < toFix.length; i++) {
    const broken = toFix[i];
    const original = mintData[broken.mintAddress];

    // Extract character name from original name: "Holy Chip #016 - MACACO-SPACE" -> "MACACO-SPACE"
    const charMatch = original.name.match(/- (.+)$/);
    const charFolder = charMatch ? charMatch[1] : 'Unknown';
    const englishName = TRANSLATIONS[charFolder] || charFolder;

    // Extract number for clean name
    const numMatch = original.name.match(/#(\d+)/);
    const num = numMatch ? parseInt(numMatch[1]) : i;
    const cleanName = `Holy Chip #${String(num).padStart(3, '0')}`;

    // Find Binary attribute
    const binaryAttr = (original.attributes || []).find(a => a.trait_type === 'Binary');
    const binary = binaryAttr ? binaryAttr.value : '';

    // Rebuild complete metadata from backup
    const newAttributes = [
      ...(original.attributes || []).map(attr => {
        if (attr.trait_type === 'Character') {
          return { ...attr, value: englishName };
        }
        return attr;
      }),
      { trait_type: 'Website', value: 'www.holy-chip.com' }
    ];

    const newJson = {
      name: cleanName,
      symbol: 'HCHIP',
      description: `${englishName} - Holy Chip NFT Collection. Binary ID: ${binary}`,
      image: original.image,
      attributes: newAttributes,
      properties: {
        files: original.properties?.files || [{ uri: original.image, type: 'image/png' }],
        category: original.properties?.category || null,
        creators: original.properties?.creators || [
          { address: '4NDUZsbuGie7CsTLASP2vzcciz9gxGFSrs4W1SSck2wx', share: 75 },
          { address: '6dXJtUWHVqqxCgaFdJb71AYW6TfE5fVxAEp7gpZXQjFz', share: 25 }
        ]
      }
    };

    // Verify we have an image before uploading
    if (!newJson.image) {
      console.error(`[${i + 1}/${toFix.length}] SKIP ${cleanName} — no image in backup data!`);
      failed++;
      continue;
    }

    try {
      // Load on-chain NFT
      const nft = await metaplex.nfts().findByMint({ mintAddress: new PublicKey(broken.mintAddress) });

      // Upload corrected metadata to Arweave
      const { uri } = await metaplex.nfts().uploadMetadata(newJson);

      // Update on-chain with new URI (use gateway.irys.xyz)
      const fixedUri = uri.replace('arweave.net', 'gateway.irys.xyz');

      await metaplex.nfts().update({
        nftOrSft: nft,
        name: cleanName,
        uri: fixedUri
      });

      success++;
      console.log(`[${i + 1}/${toFix.length}] OK ${cleanName} (${englishName}) — image: ${original.image.substring(0, 50)}...`);

    } catch (err) {
      failed++;
      console.error(`[${i + 1}/${toFix.length}] FAILED ${cleanName}: ${err.message}`);
    }

    // Rate limit
    if (i < toFix.length - 1) {
      await sleep(2000);
    }
  }

  console.log(`\n--- DONE ---`);
  console.log(`Fixed: ${success}`);
  console.log(`Failed: ${failed}`);
}

main().catch(console.error);
