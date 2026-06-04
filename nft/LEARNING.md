# LEARNING.md — Holy Chip NFT Project

> **MANDATORY PROCESS:**
> - **START of every NFT task:** Read `../../LEARNING.md` (root) + `../LEARNING.md` (HolyChip) + this file.
> - **END of every NFT task:** Update this file with new learnings from the task.

---

## 1. Current State (as of 2026-03-25)

- **251 regular NFTs** minted on Solana mainnet via Sugar CLI Candy Machine
- **101 listed** on Magic Eden at 0.3 SOL each (manual listing, 10 at a time)
- **~150 remaining** to list — needs ME API key for bulk or manual effort
- All NFTs renamed to "Holy Chip #NNN" with English character attributes + website attribute
- NFTs page live at holy-chip.com/nfts.html

---

## 2. Wallets

| Wallet | Address | Purpose |
|--------|---------|---------|
| Hot (minting) | `3FbzRU63fER4WQF6TZyhiAra917U5KAEfWRCBZHNwDko` | Fees, CLI transactions, update authority |
| Cold (creator) | `4NDUZsbuGie7CsTLASP2vzcciz9gxGFSrs4W1SSck2wx` | Receives 75% of sales + royalties |
| Designer | `6dXJtUWHVqqxCgaFdJb71AYW6TfE5fVxAEp7gpZXQjFz` | Receives 25% of sales |

- Hot wallet keypair: `~/holy-chip-wallet.json`
- Each wallet = separate seed phrase, separate browser (Brave/Chrome)

---

## 3. On-Chain IDs

- **Candy Machine (251 batch):** `13xxqZizWneyAZWMG6cp3RSTkviE2MYqbg5ioAyaFLb5`
- **Collection NFT:** `8fPw6BeeLAyp1aZcxwc4E23fZ1V7Fntv3hfhLBvyhqwW`
- **Magic Eden:** https://magiceden.us/marketplace/holy_chip

---

## 4. Key Files in This Folder

| File | Purpose |
|------|---------|
| `all-mints.json` | **CRITICAL BACKUP** — original metadata for all 251 NFTs (image URLs, attributes). Never delete. |
| `rename-nfts.js` | Bulk rename script — Metaplex JS SDK, character translations, website attribute |
| `fix-107.js` | One-off fix for #107 metadata loss during rename |
| `copy-images.js` | Incremental image consolidation from Google Drive → Characters/ |
| `bulk-list.js` | Attempted bulk listing — failed (needs ME API key) |
| `rename-log.txt` | Log output from the rename operation |
| `unlisted-mints.json` | Mint addresses not yet listed on ME |
| `Characters/` | NFT images with natural binary filenames + `manifest.json` |
| `nft_original_name/` | Flat backup of all original images (no subfolders) |
| `collection/` | Sugar CLI collection config (`config.json`) |
| `test-collection/` | Test assets used during initial setup |

---

## 5. Costs Incurred

| Operation | Cost | Date | Notes |
|-----------|------|------|-------|
| Minting 251 NFTs (Sugar CLI) | ~5.09 SOL | 2026-03-24 | Should have been ~0.13 SOL with cNFTs — 40x overspend |
| Renaming 251 NFTs | ~0.36 SOL | 2026-03-25 | 251 tx + 251 Arweave uploads (~0.0014 SOL each) |
| Fixing #107 metadata | ~0.003 SOL | 2026-03-25 | 1 tx + 1 Arweave upload |

---

## 6. Gotchas & Hard-Won Lessons

### RED FLAG: Cost Transparency (Permanent Rule)
Before ANY on-chain operation: estimate cost, compare options, get approval. See `memory/feedback_nft_cost_transparency.md`.

### Never Use Sugar CLI for Bulk Minting
`sugar mint` creates expensive regular NFTs (~0.02 SOL each). Use Metaplex Bubblegum + Merkle tree for cNFTs (~0.0005 SOL each).

### Metadata Updates Cost More Than Just TX Fees
Each Metaplex `nfts().update()` also re-uploads metadata JSON to Arweave. Budget ~0.0014 SOL per NFT, not just the ~0.00001 SOL transaction fee.

### Silent Metadata Loss During Bulk Updates
`nftObj.json` can be null/empty if the old URI is broken. Spreading `...nftObj.json` into new metadata produces an empty object — image and attributes silently disappear. **Always check `nftObj.json` is not null before using it.**

### `all-mints.json` is the Safety Net
Contains original image URLs and all attributes. When on-chain metadata gets corrupted (like #107), this file is the source of truth for recovery.

### Arweave Gateway Inconsistency
`arweave.net` may return 404 for recently uploaded content. `gateway.irys.xyz` is more reliable for Irys-uploaded content. Both serve the same data eventually.

### Public RPC Rate Limits
`api.mainnet-beta.solana.com` returns 429 during bulk operations. Use 1-2s delays between calls, or get a Helius RPC key (free tier).

### Magic Eden API
- Listings endpoint: max 100 per request, paginate with `offset`
- `floorPrice` in stats is in **lamports** (divide by 1e9 for SOL)
- `/instructions/*` endpoints (sell, buy, etc.) require API key
- Read endpoints (listings, stats, tokens) are free but CORS-blocked for browsers
- Manual listing limit: 10 NFTs at a time via ME UI

### Image Storage is Permanent
Arweave/Irys image URLs never change. Only the metadata JSON URI changes on update. Original images are safe even if metadata gets corrupted.

---

## 7. Character Translations

| Folder Name | English |
|-------------|---------|
| ASTRONAUTA | Astronaut |
| BABY | Baby |
| BOT1 | Bot 1 |
| BOT2 | Bot 2 |
| BUDA-MONGE-V1 | Buddha Monk |
| CICLOPE | Cyclops |
| CONTADOR | Accountant |
| ESPIROCADO | Spiky |
| EYES-OF-LOVE | Eyes of Love |
| IRMAO-DO-PIRATA | Pirate Brother |
| JASON | Jason |
| JASON-MAD | Mad Jason |
| MACACO-SPACE | Space Monkey |
| MACHINE | Machine |
| MADMAX | Mad Max |
| MEDICO-V1 | Doctor |
| PIRATA | Pirate |
| POLICE-V1 | Police |
| ROBOT | Robot |
| TRUMP | Trump |
| VISION | Vision |
| ZURETA | Crazy |
| _TRUMP-MULTIVERSO | Trump Multiverse |
| APOCALYPTIC | Apocalyptic |

---

## 8. Pending

- [ ] Apply for Magic Eden API key (non-US Airtable form — Ricardo is in Canada)
- [ ] List remaining ~150 NFTs on ME (bulk via API key, or manual)
- [ ] Get Helius RPC key (free tier) for reliable operations
- [ ] Verify #107 image shows on ME after cache refresh
- [ ] Future batches: use Bubblegum for cNFTs, not Sugar CLI

---

*Last updated: 2026-03-25*
