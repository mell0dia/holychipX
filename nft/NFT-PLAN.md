# Holy Chip NFT — Implementation Roadmap

> **Task tracking:** All pending NFT tasks are tracked in `BACKLOG.md` (`HolyChip/website/holy-chip-site/BACKLOG.md` → NFT Project section).


## Decision Log
- **2026-02-25:** Skipped Devnet testing — faucet was down for hours. Going straight to Mainnet.
- **2026-02-25:** Removed Pinata/IPFS — using Irys/Arweave instead (no subscription, permanent, built into Sugar CLI).
- **2026-02-25:** Two-wallet setup — hot wallet for fees, cold wallet as creator for receiving sales.
- **2026-02-25:** Initial SOL funding: 30 CAD via exchange → Phantom.
- **2026-02-25:** First 5 NFTs minted on Mainnet. Total minting cost: ~0.13 SOL. Candy Machine: `2B95WXRt69heDiY6in4nKmBNTdWbgqqFHJiUYPnwqfvH`.

---

## Phase 1: Setup (Wallet, Accounts, Tools) — COMPLETE

### 1.1 Phantom Wallet — DONE
- [x] Install Phantom browser extension on **Brave** (hot wallet)
- [x] Create wallet, securely store seed phrase
- [x] Install Phantom on **Chrome** (cold wallet — separate seed phrase)
- [x] Switched to Mainnet (skipped Devnet — faucet was down)
- [x] Funded with 30 CAD worth of SOL
- **Hot wallet:** `3FbzRU63fER4WQF6TZyhiAra917U5KAEfWRCBZHNwDko`
- **Cold wallet:** `4NDUZsbuGie7CsTLASP2vzcciz9gxGFSrs4W1SSck2wx`

### 1.2 Magic Eden Creator Account — PENDING
- [ ] Go to magiceden.io → Creator Hub
- [ ] Connect Phantom wallet (Brave — hot wallet)
- [ ] Apply as a creator
- [ ] Set up creator profile with Holy Chip branding
- **Cost:** Free
- **Time:** 30 minutes (approval may take 1-3 days)

### 1.3 Solana CLI + Sugar CLI — DONE
- [x] Installed Solana CLI 3.0.15: `sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"`
- [x] Installed Sugar CLI 2.9.1: `bash <(curl -sSf https://sugar.metaplex.com/install.sh)`
- [x] Configured for **Mainnet**: `solana config set --url mainnet-beta`
- [x] Hot wallet keypair saved: `~/holy-chip-wallet.json`
- [x] CLI configured to use hot wallet: `solana config set --keypair ~/holy-chip-wallet.json`
- Devnet airdrop failed (faucet rate-limited) — skipped to Mainnet

---

## Phase 2: First Collection (Test Batch) — IN PROGRESS

### 2.1 Prepare Test Assets — DONE
- [x] Selected 5 Holy Chip characters from website repo: Chip_0, Chip_1, Chip_100, Chip_101, Chip_110
- [x] Created metadata JSON for each with name, description, attributes, rarity
- [x] Placed images + JSONs in `test-collection/assets/` folder
- [x] Created collection.json and collection.png
- [x] Validated with `sugar validate` — passed
- [x] Set cold wallet as creator in all metadata files

**Assets location:** `HolyChip/nft/test-collection/assets/`
```
assets/
├── 0.png + 0.json  (Chip_0 — Legendary)
├── 1.png + 1.json  (Chip_1 — Legendary)
├── 2.png + 2.json  (Chip_100 — Rare)
├── 3.png + 3.json  (Chip_101 — Rare)
├── 4.png + 4.json  (Chip_110 — Common)
├── collection.png + collection.json
```

### 2.2 Metadata Format (Metaplex Standard)
```json
{
  "name": "Holy Chip #001 — Chip_0",
  "symbol": "HCHIP",
  "description": "Chip_0 — The Origin. The first character in the Holy Chip binary universe.",
  "image": "0.png",
  "attributes": [
    { "trait_type": "Character", "value": "Chip_0" },
    { "trait_type": "Binary", "value": "0" },
    { "trait_type": "Series", "value": "Genesis" },
    { "trait_type": "Rarity", "value": "Legendary" }
  ],
  "properties": {
    "files": [{ "uri": "0.png", "type": "image/png" }],
    "creators": [{ "address": "4NDUZsbuGie7CsTLASP2vzcciz9gxGFSrs4W1SSck2wx", "share": 100 }]
  }
}
```

### 2.3 Deploy & Mint on Mainnet — DONE
- [x] Sent ~0.19 SOL from Phantom to hot wallet
- [x] Created Sugar `config.json` (`uploadMethod: "bundlr"`, `sellerFeeBasisPoints: 500`)
- [x] Uploaded assets to Arweave via Irys: `sugar upload`
- [x] Deployed Candy Machine: `sugar deploy`
- [x] Verified: `sugar verify`
- [x] Minted 5 NFTs: `sugar mint --number 5`
- **Actual cost:** ~0.13 SOL (~$26)
- **Remaining balance:** 0.063 SOL

**On-chain IDs:**
- Candy Machine: `2B95WXRt69heDiY6in4nKmBNTdWbgqqFHJiUYPnwqfvH`
- Collection NFT: `6eWMqCpCXUTUHE4qbbfCXRdnsKUM9DxtvxxXNnVBEGaG`
- Solana FM: https://www.solana.fm/address/2B95WXRt69heDiY6in4nKmBNTdWbgqqFHJiUYPnwqfvH?cluster=mainnet-alpha

### 2.4 Validate — IN PROGRESS
- [x] Confirm NFTs appear in Phantom wallet — **confirmed**
- [ ] List one on Magic Eden as a test
- [ ] Verify metadata, image, attributes display correctly on Magic Eden

---

## Phase 3: Full Collection & Bulk Minting — NOT STARTED

### 3.1 Expand to All 12 Characters
- [ ] Prepare all 12 characters with full metadata
- [ ] Deploy Candy Machine
- [ ] Mint as cNFTs (compressed for cost savings)
- [ ] List on Magic Eden

### 3.2 Pricing Strategy
- Common characters: 0.5-1 SOL ($100-200)
- Rare/special editions: 2-5 SOL ($400-1000)
- Collections/bundles: 3-10 SOL
- Royalties: 5% on secondary sales

---

## Phase 4: Website Integration (nfts.html) — NOT STARTED

### 4.1 Magic Eden API Integration
- [ ] Use Magic Eden API v2 to fetch listed NFTs
- [ ] Display NFT gallery on holy-chip.com/nfts.html
- [ ] Each NFT card links to its Magic Eden listing
- [ ] Show price, status (available/sold), image

### 4.2 API Endpoints
```
GET https://api-mainnet.magiceden.dev/v2/collections/{symbol}/listings
GET https://api-mainnet.magiceden.dev/v2/collections/{symbol}/stats
```

### 4.3 Page Design
- Grid layout matching existing store.html style
- NFT cards with: image, name, price in SOL, "Buy on Magic Eden" button
- Collection stats: floor price, total volume, listed count
- Filter by character, rarity, price range

### 4.4 Implementation
- Pure HTML/CSS/JS (consistent with existing site)
- Fetch from Magic Eden API client-side
- Fallback to static data if API is down
- **Cost:** Free (API is public)

---

## Phase 5: Automation Pipeline — NOT STARTED

### 5.1 Batch Processing Script
- [ ] Script to: take folder of images → generate metadata → upload to Arweave → mint cNFTs
- [ ] Input: folder of PNGs + CSV with names/attributes
- [ ] Output: minted cNFTs listed on Magic Eden

### 5.2 Monthly Drop Workflow
1. Generate AI images (existing process)
2. Run batch script to mint + list
3. Website auto-updates via Magic Eden API
4. Announce on social media

### 5.3 Monitoring
- Track sales via Magic Eden dashboard
- Track royalty payments in cold wallet
- Monthly revenue reporting

---

## Cost Summary

| Item | One-time | Monthly |
|------|----------|---------|
| SOL funding | 30 CAD (~0.19 SOL) | As needed |
| 200 cNFTs minting | — | ~0.1 SOL ($20) |
| Irys/Arweave storage | — | ~0.2 SOL per 200 files (pay-per-use from wallet) |
| Magic Eden | — | Free (2% on sales) |
| Domain/hosting | Already have | Already have |
| **Total startup** | **30 CAD** | **$0/mo (no subscriptions)** |

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Setup | 1 day | **MOSTLY DONE** (Magic Eden creator pending) |
| Phase 2: Test batch | 1-2 days | **MOSTLY DONE** (5 NFTs minted, testing Magic Eden listing) |
| Phase 3: Full collection | 1 day | Not started |
| Phase 4: Website integration | 2-3 days | Not started |
| Phase 5: Automation | 3-5 days | Not started |
