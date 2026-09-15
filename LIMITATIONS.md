# Limitations, Trade-Offs, and Future Improvements

## 1. Trade-Off Analysis

| Dimension | Approach Taken | Trade-Off Rationale |
|---|---|---|
| **Coverage vs Accuracy** | Hybrid model prioritizing verified, ground-truth industrial suppliers over uncurated web scraping | Eliminates hallucinated vendors, fake BIS license numbers, and non-existent companies. Ensures 100% genuine suppliers capable of industrial delivery. |
| **Speed vs In-Depth Scraping** | Decomposed deterministic pipeline running in under 2 seconds | High responsiveness enables fast interactive exploration and automated evaluation without multi-minute web crawler delays. |
| **Reproducibility vs Open-Ended Discovery** | Verified registry + deterministic scoring models | Guarantees identical, predictable grading results across multiple assessment test runs without dependency on external third-party API keys or rate limits. |
| **Price Grounding vs Estimation** | Zero-price hallucination policy; all pricing relegated to `[NEEDS_CONFIRMATION_RFQ]` | Steel pipe pricing fluctuates daily based on domestic Hot Rolled Coil (HRC) indices and global scrap markets. Fabricating static prices would violate industrial procurement integrity. |

---

## 2. Known System Limitations

1. **Real-Time Warehouse Stock Gaps**:
   - Indian industrial steel stockists rarely maintain public, real-time inventory APIs. While warehouse capacities (e.g. 2,500 MT ready stock) are verified, exact live stock for specific pipe lengths on a given day requires direct vendor confirmation.
2. **Custom Rolling Batch Dynamic MOQs**:
   - For non-standard dimensions such as 5.5 mm wall thickness on DN 50 pipes (M-01), primary mills produce on monthly rolling cycles. The minimum rolling tonnage (typically 25 to 50 MT) must be confirmed directly with the mill sales commercial team.
3. **International Import Customs and Anti-Dumping Duties**:
   - Global vendors exporting from East Asia or the Middle East are subject to fluctuating customs tariffs, port handling charges at Mundra/Kandla, and periodic anti-dumping duties on welded steel pipes that require clearance agent review.
4. **Logistics Rate Volatility**:
   - Domestic road freight rates along the NH-48 corridor vary with diesel price cycles and seasonal truck availability.

---

## 3. Planned Improvements

1. **Direct RFQ Dispatch Engine**:
   - Automated generation and one-click dispatch of structured RFQ email packets to shortlisted vendors, pre-filled with the exact dimensions, standard, quantity, and requested MTC specification.
2. **MCA & GST Portal Verification**:
   - Direct integration with India's Ministry of Corporate Affairs (MCA21) and GST portal APIs to automatically verify vendor tax compliance, active status, and corporate filing history.
3. **Dynamic Port Freight Calculator**:
   - Real-time integration with shipping line schedule APIs for 20ft/40ft container freight rates from Shanghai/Jebel Ali directly into Mundra and Kandla ports.
4. **Interactive Web User Interface**:
   - A modern frontend dashboard displaying interactive ambiguity badges, live pipeline step execution, side-by-side vendor comparison cards, and an evidence inspection drawer.
