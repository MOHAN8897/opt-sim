#!/usr/bin/env node

/**
 * Helper script to start ngrok tunnel and display URL
 * This runs alongside Vite to show the public ngrok URL
 */

const { exec } = require('child_process');
const http = require('http');

const NGROK_API = 'http://localhost:4040/api/tunnels';
const PORT = 5173;
const MAX_RETRIES = 10;
const RETRY_DELAY = 1000;

let ngrokProcess = null;
let retryCount = 0;

// Colors for console output
const colors = {
    reset: '\x1b[0m',
    cyan: '\x1b[36m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    gray: '\x1b[90m',
    red: '\x1b[31m'
};

function log(message, color = colors.reset) {
    console.log(`${color}${message}${colors.reset}`);
}

function startNgrok() {
    log('\n🌐 Starting ngrok tunnel for frontend...', colors.cyan);

    // Start ngrok process
    ngrokProcess = exec(`ngrok http ${PORT}`, (error) => {
        if (error && !error.killed) {
            log(`❌ ngrok error: ${error.message}`, colors.red);
        }
    });

    // Wait a bit for ngrok to start, then fetch URL
    setTimeout(fetchNgrokUrl, 2000);
}

function fetchNgrokUrl() {
    http.get(NGROK_API, (res) => {
        let data = '';

        res.on('data', (chunk) => {
            data += chunk;
        });

        res.on('end', () => {
            try {
                const response = JSON.parse(data);

                if (response.tunnels && response.tunnels.length > 0) {
                    const tunnel = response.tunnels.find(t => t.config.addr.includes(PORT.toString()));

                    if (tunnel) {
                        const publicUrl = tunnel.public_url;
                        displayUrls(publicUrl);
                    } else {
                        retryFetch();
                    }
                } else {
                    retryFetch();
                }
            } catch (error) {
                retryFetch();
            }
        });
    }).on('error', () => {
        retryFetch();
    });
}

function retryFetch() {
    retryCount++;
    if (retryCount < MAX_RETRIES) {
        setTimeout(fetchNgrokUrl, RETRY_DELAY);
    } else {
        log('⚠️  Could not fetch ngrok URL. Check http://localhost:4040 manually.', colors.yellow);
    }
}

function displayUrls(ngrokUrl) {
    log('\n═══════════════════════════════════════════════', colors.gray);
    log('  📱 SHARE THIS URL WITH FRIENDS:', colors.green);
    log(`     ${ngrokUrl}`, colors.green);
    log('\n  🏠 Local development:', colors.gray);
    log(`     http://localhost:${PORT}`, colors.gray);
    log('═══════════════════════════════════════════════\n', colors.gray);

    // Save to file
    require('fs').writeFileSync('.ngrok-frontend-url', ngrokUrl);
}

// Handle cleanup
process.on('SIGINT', () => {
    if (ngrokProcess) {
        ngrokProcess.kill();
    }
    process.exit();
});

process.on('SIGTERM', () => {
    if (ngrokProcess) {
        ngrokProcess.kill();
    }
    process.exit();
});

// Start ngrok
startNgrok();

// Keep the process running
setInterval(() => { }, 1000);
