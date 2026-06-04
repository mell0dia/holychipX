# Holy Chip NFT Project

> **Task tracking:** All pending NFT tasks are tracked in `BACKLOG.md` (`HolyChip/website/holy-chip-site/BACKLOG.md` → NFT Project section).


## Vision
Sell AI-generated Holy Chip character images as Solana NFTs on Magic Eden, displayed and linked from holy-chip.com/nfts.html.

## Scale
- Hundreds of new AI-generated images per month
- Use **compressed NFTs (cNFTs)** for cost efficiency at scale (~$0.0005/mint vs ~$2/regular NFT)
- Batch minting via Metaplex Candy Machine v3

## Architecture
```
AI Images → Irys/Arweave (permanent storage) → Metaplex Candy Machine → Solana (cNFTs) → Magic Eden → holy-chip.com/nfts.html
```

## Wallets (Two-Wallet Security Setup)

| Wallet | Address | Purpose | Browser |
|--------|---------|---------|---------|
| **Hot Wallet** | `3FbzRU63fER4WQF6TZyhiAra917U5KAEfWRCBZHNwDko` | Minting fees, listing, CLI transactions | Brave (Phantom) |
| **Cold Wallet** | `4NDUZsbuGie7CsTLASP2vzcciz9gxGFSrs4W1SSck2wx` | Creator address — receives all sales + royalties | Chrome (Phantom) |

- Hot wallet keypair file: `~/holy-chip-wallet.json`
- Each wallet has a **separate seed phrase** (different browsers)
- Keep only small amounts in hot wallet (~0.1-0.5 SOL for fees)
- Cold wallet is set as `creator` in all NFT metadata — sales go directly there

## Key Components
| Component | Tool | Purpose |
|-----------|------|---------|
| Wallet | Phantom (Brave + Chrome) | Hot wallet for minting, cold wallet for receiving |
| Marketplace | Magic Eden | List and sell NFTs (largest Solana marketplace) |
| Minting | Metaplex Candy Machine v3 | Bulk mint cNFTs with configurable drops |
| Image Storage | Irys → Arweave | Permanent decentralized storage, paid from SOL wallet |
| CLI Tools | Solana CLI 3.0.15 + Sugar CLI 2.9.1 | Command-line minting and deployment |

## Workflow
1. Generate AI images (existing process)
2. Sugar CLI uploads images + metadata to Arweave via Irys (automatic)
3. Configure Candy Machine collection
4. Mint cNFTs on Solana
5. List on Magic Eden
6. Display on holy-chip.com/nfts.html with Magic Eden links

## Costs (Estimated)
- **Solana transactions:** ~0.00001 SOL per tx (~$0.002)
- **cNFT minting:** ~0.0005 SOL per NFT (~$0.10 for 200 NFTs)
- **Irys/Arweave storage:** ~0.001 SOL per file (paid from wallet, no subscription)
- **Magic Eden listing:** Free (2% seller fee on sales)
- **Candy Machine creation:** ~0.02 SOL one-time

## CLI Configuration
```
Solana CLI: 3.0.15
Sugar CLI: 2.9.1
Network: mainnet-beta
RPC: https://api.mainnet-beta.solana.com
Keypair: ~/holy-chip-wallet.json (hot wallet)
```

## Repository
- Main site: https://github.com/mell0dia/holy-chip-site.git (gh-pages branch)
- NFT docs: This folder (`HolyChip/nft/`)
- Test collection assets: `test-collection/assets/`

## Tool Documentation
See `tools/` subfolder for detailed setup guides:
- `phantom-wallet.md` — Wallet setup
- `magic-eden.md` — Marketplace setup
- `metaplex-candy-machine.md` — Bulk minting
- `irys-arweave.md` — Permanent image/metadata storage
- `solana-cli.md` — CLI tools
