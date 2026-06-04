#!/usr/bin/env node

/**
 * Rename all Holy Chip NFTs on-chain.
 * - Name: "Holy Chip #001" (sequential, zero-padded to 3 digits)
 * - Character folder name → English translation as attribute
 * - Uses update authority (hot wallet) to update mutable metadata
 */

const { Metaplex, keypairIdentity } = require('@metaplex-foundation/js');
const { Connection, Keypair } = require('@solana/web3.js');
const fs = require('fs');

const RPC = 'https://api.mainnet-beta.solana.com';
const connection = new Connection(RPC, 'confirmed');
const keypair = Keypair.fromSecretKey(
  Uint8Array.from(JSON.parse(fs.readFileSync(process.env.HOME + '/holy-chip-wallet.json')))
);

const metaplex = Metaplex.make(connection).use(keypairIdentity(keypair));

// Character name translations
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

function translateCharacter(folderName) {
  return TRANSLATIONS[folderName] || folderName;
}

// Extract character from current name: "Holy Chip #016 - MACACO-SPACE" -> "MACACO-SPACE"
function extractCharacter(name) {
  const match = name.match(/- (.+)$/);
  return match ? match[1] : 'Unknown';
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const allMints = JSON.parse(fs.readFileSync('all-mints.json', 'utf8'));

  // Sort by current number to maintain consistent ordering
  allMints.sort((a, b) => {
    const numA = parseInt(a.name.match(/#(\d+)/)?.[1] || '0');
    const numB = parseInt(b.name.match(/#(\d+)/)?.[1] || '0');
    return numA - numB;
  });

  console.log(`Updating ${allMints.length} NFTs...\n`);

  let success = 0;
  let failed = 0;

  for (let i = 0; i < allMints.length; i++) {
    const nft = allMints[i];
    const mintAddress = nft.mintAddress;
    const oldName = nft.name;
    const character = extractCharacter(oldName);
    const englishName = translateCharacter(character);

    // Extract current number from name
    const numMatch = oldName.match(/#(\d+)/);
    const num = numMatch ? parseInt(numMatch[1]) : i;
    const newName = `Holy Chip #${String(num).padStart(3, '0')}`;

    try {
      // Load on-chain NFT
      const nftObj = await metaplex.nfts().findByMint({ mintAddress: new (require('@solana/web3.js').PublicKey)(mintAddress) });

      // Update the character attribute to English translation
      let newAttributes = (nftObj.json?.attributes || []).map(attr => {
        if (attr.trait_type === 'Character') {
          return { ...attr, value: englishName };
        }
        return attr;
      });

      // Add website attribute if not already there
      if (!newAttributes.find(a => a.trait_type === 'Website')) {
        newAttributes.push({ trait_type: 'Website', value: 'www.holy-chip.com' });
      }

      // Build new URI JSON with updated name and attributes
      const newJson = {
        ...nftObj.json,
        name: newName,
        description: `${englishName} - Holy Chip NFT Collection. Binary ID: ${nftObj.json?.attributes?.find(a => a.trait_type === 'Binary')?.value || ''}`,
        attributes: newAttributes
      };

      // Upload new metadata JSON
      const { uri } = await metaplex.nfts().uploadMetadata(newJson);

      // Update on-chain
      await metaplex.nfts().update({
        nftOrSft: nftObj,
        name: newName,
        uri: uri
      });

      success++;
      console.log(`[${i + 1}/${allMints.length}] ${oldName} -> ${newName} (${englishName})`);

    } catch (err) {
      failed++;
      console.error(`[${i + 1}/${allMints.length}] FAILED ${oldName}: ${err.message}`);
    }

    // Small delay to avoid rate limits
    if (i < allMints.length - 1) {
      await sleep(1500);
    }
  }

  console.log(`\n--- DONE ---`);
  console.log(`Updated: ${success}`);
  console.log(`Failed: ${failed}`);
}

main().catch(console.error);
