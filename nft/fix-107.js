#!/usr/bin/env node

/**
 * Fix Holy Chip #107 — metadata was lost during rename.
 * Re-uploads correct metadata with image, attributes, and website.
 * Cost: ~0.003 SOL
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

const MINT = '7RJqNb5w3mPDMVq9mfxJi3WCxc3xaEfA9R2831Wy1Pcs';
const IMAGE = 'https://gateway.irys.xyz/DW7I8e7Z2yQyDWugzMmIV01JrTtPm4pTszMzFTsM4LI?ext=png';

async function main() {
  console.log('Loading NFT #107...');
  const nft = await metaplex.nfts().findByMint({ mintAddress: new PublicKey(MINT) });
  console.log('Current name:', nft.name);
  console.log('Current URI:', nft.uri);

  const newJson = {
    name: 'Holy Chip #107',
    symbol: 'HCHIP',
    description: 'Eyes of Love - Holy Chip NFT Collection. Binary ID: 1101011',
    image: IMAGE,
    attributes: [
      { trait_type: 'Character', value: 'Eyes of Love' },
      { trait_type: 'Binary', value: '1101011' },
      { trait_type: 'Outfit', value: '322' },
      { trait_type: 'Background', value: '115' },
      { trait_type: 'Right Hand', value: '27' },
      { trait_type: 'Mouth', value: '1' },
      { trait_type: 'Accessory', value: '46' },
      { trait_type: 'Website', value: 'www.holy-chip.com' }
    ],
    properties: {
      files: [{ uri: IMAGE, type: 'image/png' }],
      category: null,
      creators: [
        { address: '4NDUZsbuGie7CsTLASP2vzcciz9gxGFSrs4W1SSck2wx', share: 75 },
        { address: '6dXJtUWHVqqxCgaFdJb71AYW6TfE5fVxAEp7gpZXQjFz', share: 25 }
      ]
    }
  };

  console.log('Uploading corrected metadata...');
  const { uri } = await metaplex.nfts().uploadMetadata(newJson);
  console.log('New URI:', uri);

  console.log('Updating on-chain...');
  await metaplex.nfts().update({
    nftOrSft: nft,
    name: 'Holy Chip #107',
    uri: uri
  });

  console.log('Done! Holy Chip #107 fixed.');
}

main().catch(console.error);
