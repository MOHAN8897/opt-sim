/**
 * 🆕 Market Data API Integration Guide
 * 
 * This guide shows how to use the new optimized market data endpoints
 * from your frontend to fetch Option Chain details (LTP, OI, IV, Greeks)
 * 
 * These endpoints work seamlessly for both:
 * ✅ MARKET OPEN - Live data with Greeks
 * ✅ MARKET CLOSED - Last session data with fallbacks
 */

// ============================================================================
// 1️⃣ FETCH SPOT LTP (Last Traded Price)
// ============================================================================

/**
 * Get the current or last-traded price of a spot instrument
 * 
 * 🟢 Market OPEN: Returns live LTP
 * 🔴 Market CLOSED: Returns previous day close (fallback)
 * 
 * @param {string} instrumentKey - e.g., "NSE_INDEX|Nifty 50"
 * @returns {Promise<Object>} Spot price data
 */
async function getSpotLTP(instrumentKey) {
  const response = await fetch(
    `/api/market/ltp-v3?instrument_key=${encodeURIComponent(instrumentKey)}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch LTP: ${response.status}`);
  }

  return response.json();
  // Response:
  // {
  //   "ltp": 24500.5,
  //   "market_status": "OPEN",  // or "CLOSED" or "UNKNOWN"
  //   "volume": 1500000,
  //   "previous_close": 24400.0,
  //   "timestamp": "2025-01-21 15:30:00",
  //   "ltq": 50
  // }
}

// ============================================================================
// 2️⃣ FETCH FULL OPTION CHAIN (LTP, OI, IV, GREEKS) ⭐ RECOMMENDED
// ============================================================================

/**
 * Get complete option chain with all details
 * BEST endpoint for displaying option chains to users
 * 
 * 🟢 Market OPEN: 
 *    - LTP from live data
 *    - IV and Greeks included
 * 🔴 Market CLOSED:
 *    - LTP, OI persisted from last session
 *    - IV and Greeks set to 0 (market closed)
 * 
 * @param {string} instrumentKey - Underlying e.g., "NSE_INDEX|Nifty 50"
 * @param {string} expiryDate - Date in YYYY-MM-DD format
 * @returns {Promise<Object>} Full option chain with quotes
 */
async function getOptionChain(instrumentKey, expiryDate) {
  const response = await fetch(
    `/api/market/option-chain-v3?instrument_key=${encodeURIComponent(
      instrumentKey
    )}&expiry_date=${expiryDate}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch option chain: ${response.status}`);
  }

  const data = await response.json();
  
  // Response:
  // {
  //   "spot_price": 24500.5,
  //   "atm_strike": 24500,
  //   "market_status": "OPEN",
  //   "chain": [
  //     {
  //       "strike_price": 24400,
  //       "call_options": {
  //         "instrument_key": "NSE_FO|58725",
  //         "trading_symbol": "NIFTY24D2424400CE",
  //         "ltp": 245.5,
  //         "oi": 1250000,
  //         "iv": 18.5,
  //         "delta": 0.65,
  //         "gamma": 0.012,
  //         "theta": -0.045,
  //         "vega": 0.125,
  //         "volume": 2500000,
  //         "bid": 245.0,
  //         "ask": 245.5
  //       },
  //       "put_options": {
  //         "instrument_key": "NSE_FO|58726",
  //         "trading_symbol": "NIFTY24D2424400PE",
  //         "ltp": 215.25,
  //         "oi": 980000,
  //         "iv": 18.2,
  //         "delta": -0.35,
  //         "gamma": 0.012,
  //         "theta": -0.035,
  //         "vega": 0.120,
  //         "volume": 1800000,
  //         "bid": 215.0,
  //         "ask": 215.5
  //       },
  //       "market_status": "OPEN"
  //     },
  //     // ... more strikes
  //   ],
  //   "timestamp": "2025-01-21T15:30:00.000Z"
  // }

  return data;
}

// ============================================================================
// 3️⃣ FETCH BATCH OPTION QUOTES (LTP, OI, IV, GREEKS)
// ============================================================================

/**
 * Get quotes for multiple option instruments at once
 * More efficient than fetching individually
 * 
 * 🟢 Market OPEN: Uses /v3/market-quote/option-greek (includes Greeks)
 * 🔴 Market CLOSED: Uses /v2/market-quote/full (persists last session data)
 * 
 * @param {string[]} instrumentKeys - Array of instrument keys or comma-separated string
 * @returns {Promise<Object>} Map of instrument_key -> quote data
 */
async function getOptionQuotesBatch(instrumentKeys) {
  // Convert array to comma-separated string if needed
  const keysParam = Array.isArray(instrumentKeys) 
    ? instrumentKeys.join(',') 
    : instrumentKeys;

  const response = await fetch(
    `/api/market/option-quotes-batch-v3?instrument_key=${encodeURIComponent(
      keysParam
    )}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch option quotes: ${response.status}`);
  }

  return response.json();
  // Response:
  // {
  //   "NSE_FO|58725": {
  //     "ltp": 245.5,
  //     "oi": 1250000,
  //     "iv": 18.5,
  //     "delta": 0.65,
  //     "gamma": 0.012,
  //     "theta": -0.045,
  //     "vega": 0.125,
  //     "volume": 2500000,
  //     "bid": 245.0,
  //     "ask": 245.5,
  //     "bid_quantity": 500,
  //     "ask_quantity": 500,
  //     "previous_close": 244.0,
  //     "timestamp": "2025-01-21 15:30:00",
  //     "market_status": "OPEN"
  //   },
  //   "NSE_FO|58726": {
  //     // ... similar structure
  //   }
  // }
}

// ============================================================================
// 4️⃣ FETCH IV AND GREEKS ONLY
// ============================================================================

/**
 * Get IV and Greeks for multiple options
 * Useful when you only need Greeks data
 * 
 * Returns zeros for Greeks when market is closed
 * 
 * @param {string[]} instrumentKeys - Array of instrument keys
 * @returns {Promise<Object>} Map of instrument_key -> greeks
 */
async function getOptionGreeks(instrumentKeys) {
  const keysParam = Array.isArray(instrumentKeys) 
    ? instrumentKeys.join(',') 
    : instrumentKeys;

  const response = await fetch(
    `/api/market/option-iv-greeks-batch?instrument_key=${encodeURIComponent(
      keysParam
    )}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch Greeks: ${response.status}`);
  }

  return response.json();
  // Response:
  // {
  //   "NSE_FO|58725": {
  //     "iv": 18.5,
  //     "delta": 0.65,
  //     "gamma": 0.012,
  //     "theta": -0.045,
  //     "vega": 0.125,
  //     "market_status": "OPEN"
  //   }
  // }
}

// ============================================================================
// 🎯 PRACTICAL EXAMPLES
// ============================================================================

// EXAMPLE 1: Display Option Chain in UI (WITH MARKET-CLOSED HANDLING)
async function displayOptionChain() {
  try {
    const data = await getOptionChain('NSE_INDEX|Nifty 50', '2025-02-27');
    
    console.log(`Spot Price: ${data.spot_price}`);
    console.log(`ATM Strike: ${data.atm_strike}`);
    console.log(`Market Status: ${data.market_status}`);
    console.log(`Timestamp: ${data.timestamp}`);
    
    // ✅ CRITICAL: Check market status for EACH ROW
    data.chain.forEach(row => {
      const callData = row.call_options;
      const putData = row.put_options;
      const rowStatus = row.market_status;
      
      // 🔴 When market CLOSED: Greeks are zeros (correct behavior)
      if (rowStatus === 'CLOSED') {
        console.log(`
          Strike: ${row.strike_price} [MARKET CLOSED - Last Session Data]
          CALL: LTP=${callData.ltp}, OI=${callData.oi}, IV=0 (N/A), Δ=0 (N/A)
          PUT:  LTP=${putData.ltp}, OI=${putData.oi}, IV=0 (N/A), Δ=0 (N/A)
          ⚠️ Greeks are zeros because market is closed. They will update when market opens.
        `);
      } else {
        // 🟢 When market OPEN: Greeks are live
        console.log(`
          Strike: ${row.strike_price} [Market OPEN]
          CALL: LTP=${callData.ltp}, OI=${callData.oi}, IV=${callData.iv}, Δ=${callData.delta}
          PUT:  LTP=${putData.ltp}, OI=${putData.oi}, IV=${putData.iv}, Δ=${putData.delta}
        `);
      }
    });
  } catch (error) {
    console.error('Failed to display option chain:', error);
  }
}

// EXAMPLE 2: Update Option Chain When Market Closed (WITH UI INDICATORS)
async function updateOptionChainMarketClosed() {
  try {
    const data = await getOptionChain('NSE_INDEX|Nifty 50', '2025-02-27');
    
    console.log(`\n=== OPTION CHAIN UPDATE ===`);
    console.log(`Status: ${data.market_status}`);
    console.log(`Spot: ${data.spot_price}`);
    console.log(`Time: ${data.timestamp}`);
    
    if (data.market_status === 'CLOSED') {
      console.log('\n🔴 MARKET CLOSED - Displaying Last Trading Session Data');
      console.log('   - Spot Price: Last closing price (will not update)');
      console.log('   - Option LTP: Last traded price of the session');
      console.log('   - Option OI: Open Interest at market close');
      console.log('   - Greeks (Δ,Γ,Θ,Ν): All zeros (market closed)');
      console.log('   - IV: Zero (market closed)');
      console.log('\n✅ Data is SECURE. All values are from last trading session.');
      console.log('✅ Greeks will update when market opens next trading day.\n');
      
      // UI UPDATES FOR MARKET CLOSED:
      // 1. Show badge "Market Closed"
      // 2. Show last update time
      // 3. Gray out all Greeks columns
      // 4. Disable live price WebSocket updates
      // 5. Show message: "Data from previous trading session"
      
      updateUI('market-badge', 'CLOSED');
      updateUI('last-update-time', new Date(data.timestamp).toLocaleString('en-IN', { 
        timeZone: 'Asia/Kolkata' 
      }));
      disableGreeksDisplay();
      stopWebSocketUpdates();
      showMessage('Data from previous trading session');
    } else if (data.market_status === 'OPEN') {
      console.log('\n🟢 MARKET OPEN - Displaying Live Data');
      
      // UI UPDATES FOR MARKET OPEN:
      // 1. Hide "Market Closed" badge
      // 2. Show live update indicator
      // 3. Enable Greeks columns
      // 4. Start WebSocket updates
      // 5. Show "Live" indicator
      
      updateUI('market-badge', 'OPEN');
      updateUI('last-update-time', 'LIVE');
      enableGreeksDisplay();
      startWebSocketUpdates();
      showMessage('Live market data');
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

// ✨ NEW: Helper function to render table with market-aware styling
async function renderOptionChainTable(instrumentKey, expiryDate) {
  try {
    const data = await getOptionChain(instrumentKey, expiryDate);
    
    const table = `
      <div class="option-chain-container">
        <!-- Header Section -->
        <div class="header">
          <div class="spot-info">
            <span>Spot: ${data.spot_price}</span>
            <span>ATM: ${data.atm_strike}</span>
            <span class="market-status-badge ${data.market_status.toLowerCase()}">
              ${data.market_status}
            </span>
          </div>
          <div class="timestamp">${data.timestamp}</div>
        </div>
        
        <!-- Chain Table -->
        <table class="option-chain">
          <thead>
            <tr>
              <th>Call OI</th>
              <th>Call IV</th>
              <th>Call Δ</th>
              <th>Strike</th>
              <th>Put Δ</th>
              <th>Put IV</th>
              <th>Put OI</th>
            </tr>
          </thead>
          <tbody>
            ${data.chain.map(row => `
              <tr class="row-${row.market_status.toLowerCase()}">
                <td>${row.call_options.oi}</td>
                <td class="greeks-cell ${row.market_status === 'CLOSED' ? 'disabled' : ''}">
                  ${row.market_status === 'CLOSED' ? '-' : row.call_options.iv.toFixed(2)}
                </td>
                <td class="greeks-cell ${row.market_status === 'CLOSED' ? 'disabled' : ''}">
                  ${row.market_status === 'CLOSED' ? '-' : row.call_options.delta.toFixed(2)}
                </td>
                <td class="strike-price">${row.strike_price}</td>
                <td class="greeks-cell ${row.market_status === 'CLOSED' ? 'disabled' : ''}">
                  ${row.market_status === 'CLOSED' ? '-' : row.put_options.delta.toFixed(2)}
                </td>
                <td class="greeks-cell ${row.market_status === 'CLOSED' ? 'disabled' : ''}">
                  ${row.market_status === 'CLOSED' ? '-' : row.put_options.iv.toFixed(2)}
                </td>
                <td>${row.put_options.oi}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        
        <!-- Footer -->
        <div class="footer">
          ${data.market_status === 'CLOSED' 
            ? '<p>⚠️ Market Closed. Data from last trading session. Greeks will update when market opens.</p>'
            : '<p>🟢 Live market data. Updating every 5 seconds.</p>'
          }
        </div>
      </div>
    `;
    
    return table;
  } catch (error) {
    console.error('Failed to render table:', error);
  }
}

// ✨ NEW: CSS Styles for market-closed state
const optionChainStyles = `
  .row-closed {
    background-color: #f5f5f5;
    opacity: 0.7;
  }
  
  .greeks-cell.disabled {
    color: #999;
    font-style: italic;
  }
  
  .market-status-badge {
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: bold;
    font-size: 12px;
  }
  
  .market-status-badge.open {
    background-color: #d4edda;
    color: #155724;
  }
  
  .market-status-badge.closed {
    background-color: #f8d7da;
    color: #721c24;
  }
`

// EXAMPLE 3: Fetch ATM Options Only (Performance)
async function getATMOptions(instrumentKey, expiryDate) {
  try {
    const chain = await getOptionChain(instrumentKey, expiryDate);
    const atmStrike = chain.atm_strike;
    
    // Find ATM row
    const atmRow = chain.chain.find(r => r.strike_price === atmStrike);
    
    if (atmRow) {
      const callKey = atmRow.call_options.instrument_key;
      const putKey = atmRow.put_options.instrument_key;
      
      // Update prices periodically from batch endpoint
      const quotes = await getOptionQuotesBatch([callKey, putKey]);
      
      return {
        strike: atmStrike,
        call: quotes[callKey],
        put: quotes[putKey],
        spot: chain.spot_price,
        market_status: chain.market_status
      };
    }
  } catch (error) {
    console.error('Error fetching ATM options:', error);
  }
}

// EXAMPLE 4: Periodic Update (Live Data Polling)
async function startPricePolling(instrumentKeys, intervalMs = 5000) {
  const pollInterval = setInterval(async () => {
    try {
      const quotes = await getOptionQuotesBatch(instrumentKeys);
      
      // Update UI with new prices
      Object.entries(quotes).forEach(([key, quote]) => {
        updatePriceInUI(key, quote.ltp);
        
        // Only show Greeks when market is open
        if (quote.market_status === 'OPEN') {
          updateGreeksInUI(key, {
            iv: quote.iv,
            delta: quote.delta,
            gamma: quote.gamma,
            theta: quote.theta,
            vega: quote.vega
          });
        }
      });
    } catch (error) {
      console.error('Polling error:', error);
    }
  }, intervalMs);
  
  return () => clearInterval(pollInterval);
}

// ============================================================================
// 📌 KEY BEHAVIORS FOR MARKET CLOSED SCENARIOS
// ============================================================================

/*
When market is CLOSED (market_status = "CLOSED"):

1. LTP Values:
   - Returns LAST TRADED PRICE from previous trading session
   - Not updated until market reopens
   - Shows "As of [previous session close time]" to user

2. OI (Open Interest):
   - Shows OI from previous trading session
   - Typically not changed during market closed
   - Updated when market opens

3. IV (Implied Volatility):
   - Set to 0 (not calculated when market closed)
   - Shows "-" or "N/A" in UI
   - Updates when market opens

4. Greeks (Delta, Gamma, Theta, Vega):
   - Set to 0 (not calculated when market closed)
   - Shows "-" or "N/A" in UI
   - Updates when market opens

5. Volume:
   - Shows total volume from previous trading session
   - Not updated until market opens

FRONTEND DISPLAY:
- Add "Market Closed" badge to UI
- Gray out Greeks columns (IV, Δ, Γ, Θ, Ν)
- Show last update time: "Last updated: 15:30 IST (01-21-2025)"
- Enable WebSocket/polling for live updates when market opens
*/

// ============================================================================
// 🔧 HELPER: Check Market Status
// ============================================================================

async function checkMarketStatus(instrumentKey = 'NSE_INDEX|Nifty 50') {
  try {
    const ltp = await getSpotLTP(instrumentKey);
    return ltp.market_status;
  } catch (error) {
    console.error('Error checking market status:', error);
    return 'UNKNOWN';
  }
}

// ============================================================================
// 📊 API ENDPOINT REFERENCE TABLE
// ============================================================================

/*
Endpoint                        Purpose                    Market OPEN           Market CLOSED         Typical Use Case
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
/api/market/ltp-v3              Get spot price             Live LTP              Previous close        Current spot price
/api/market/option-chain-v3 ⭐  Full option chain          Live data + Greeks    Last session + 0s     Display chain in UI
/api/market/option-quotes-      Batch quotes               /v3 option-greek      /v2 market-quote/full Batch price update
batch-v3                        (LTP, OI, IV, Greeks)      (all fields)           (ltp, oi, vol)
/api/market/option-iv-greeks-   IV and Greeks only         Live calculations      Zeros                 Greeks analysis
batch

⭐ RECOMMENDED: Use /api/market/option-chain-v3 for displaying option chains
   It handles both market OPEN and CLOSED scenarios automatically
*/

// Export for use in other modules
export {
  getSpotLTP,
  getOptionChain,
  getOptionQuotesBatch,
  getOptionGreeks,
  checkMarketStatus,
  displayOptionChain,
  updateOptionChainMarketClosed,
  renderOptionChainTable,
  getATMOptions,
  startPricePolling,
  optionChainStyles
};
