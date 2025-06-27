# Optimized Adaptive Strategy Management Script
# Run this script to manage your optimized adaptive trading strategy

Write-Host "=== OPTIMIZED ADAPTIVE STRATEGY MANAGER ===" -ForegroundColor Cyan
Write-Host ""

# Check if freqtrade is available
if (!(Get-Command "freqtrade" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ FreqTrade not found! Please install FreqTrade first." -ForegroundColor Red
    exit
}

# Display menu
function Show-Menu {
    Write-Host "📊 Available Actions:" -ForegroundColor Yellow
    Write-Host "1. Download required data (15m, 1h, 4h) for top 10 coins"
    Write-Host "2. Run backtest on recent data (30 days)"
    Write-Host "3. Run backtest on custom date range"
    Write-Host "4. Analyze existing backtest results"
    Write-Host "5. Start paper trading"
    Write-Host "6. Start live trading (⚠️  Use with caution!)"
    Write-Host "7. View current configuration"
    Write-Host "8. Exit"
    Write-Host ""
}

# Function to download data
function Download-Data {
    $days = Read-Host "How many days of data to download? (default: 30)"
    if (!$days) { $days = 30 }
    
    Write-Host "📥 Downloading $days days of data for timeframes 15m, 1h, 4h..." -ForegroundColor Green
    Write-Host "📋 Pairs: BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT, ADA/USDT, AVAX/USDT, DOGE/USDT, DOT/USDT, MATIC/USDT" -ForegroundColor Cyan
    
    freqtrade download-data --timeframes 15m 1h 4h --days $days --config user_data/config.json
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Data download completed!" -ForegroundColor Green
    } else {
        Write-Host "❌ Data download failed!" -ForegroundColor Red
    }
}

# Function to run backtest
function Run-Backtest {
    param($timerange = $null)
    
    if (!$timerange) {
        Write-Host "📈 Running backtest on recent 30 days..." -ForegroundColor Green
        freqtrade backtesting --config user_data/config.json --strategy OptimizedAdaptiveStrategy --breakdown month
    } else {
        Write-Host "📈 Running backtest on timerange: $timerange..." -ForegroundColor Green
        freqtrade backtesting --config user_data/config.json --strategy OptimizedAdaptiveStrategy --timerange $timerange --breakdown month
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Backtest completed!" -ForegroundColor Green
        Write-Host "💡 Run option 4 to analyze the results" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Backtest failed!" -ForegroundColor Red
    }
}

# Function to analyze results
function Analyze-Results {
    Write-Host "📊 Analyzing backtest results..." -ForegroundColor Green
    
    # Check if analysis script exists
    if (Test-Path "analyze_trades.py") {
        python analyze_trades.py
    } elseif (Test-Path "strategy_analysis.py") {
        python strategy_analysis.py
    } else {
        Write-Host "❌ Analysis script not found!" -ForegroundColor Red
        Write-Host "💡 You can manually check results in user_data/backtest_results/" -ForegroundColor Yellow
    }
}

# Function to start paper trading
function Start-PaperTrading {
    Write-Host "📝 Starting paper trading with OptimizedAdaptiveStrategy..." -ForegroundColor Green
    Write-Host "💰 Pairs: Top 10 crypto coins" -ForegroundColor Cyan
    Write-Host "⚠️  This will run indefinitely. Press Ctrl+C to stop." -ForegroundColor Yellow
    
    $confirm = Read-Host "Continue? (y/N)"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        freqtrade trade --config user_data/config.json --strategy OptimizedAdaptiveStrategy
    }
}

# Function to start live trading
function Start-LiveTrading {
    Write-Host "🚨 LIVE TRADING WARNING 🚨" -ForegroundColor Red
    Write-Host "This will use real money! Make sure you've:" -ForegroundColor Red
    Write-Host "- Thoroughly tested the strategy" -ForegroundColor Red
    Write-Host "- Set proper API keys in config" -ForegroundColor Red
    Write-Host "- Configured risk management" -ForegroundColor Red
    Write-Host "- Set dry_run: false in config" -ForegroundColor Red
    Write-Host ""
    
    $confirm = Read-Host "Are you absolutely sure? Type 'LIVE TRADING' to confirm"
    if ($confirm -eq "LIVE TRADING") {
        freqtrade trade --config user_data/config.json --strategy OptimizedAdaptiveStrategy
    } else {
        Write-Host "❌ Live trading cancelled." -ForegroundColor Yellow
    }
}

# Function to show configuration
function Show-Config {
    Write-Host "📋 Current Configuration:" -ForegroundColor Green
    Write-Host "Strategy: OptimizedAdaptiveStrategy" -ForegroundColor Cyan
    Write-Host "Timeframe: 15m (with 1h and 4h higher timeframes)" -ForegroundColor Cyan
    Write-Host "Max Open Trades: 3" -ForegroundColor Cyan
    Write-Host "Stake Amount: 20 USDT" -ForegroundColor Cyan
    Write-Host "Dry Run: true" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Trading Pairs:" -ForegroundColor Yellow
    Write-Host "• BTC/USDT  • ETH/USDT  • BNB/USDT  • SOL/USDT  • XRP/USDT" -ForegroundColor Gray
    Write-Host "• ADA/USDT  • AVAX/USDT • DOGE/USDT • DOT/USDT  • MATIC/USDT" -ForegroundColor Gray
    Write-Host ""
}

# Main menu loop
do {
    Show-Menu
    $choice = Read-Host "Select an option (1-8)"
    
    switch ($choice) {
        "1" { Download-Data }
        "2" { Run-Backtest }
        "3" { 
            $range = Read-Host "Enter timerange (format: YYYYMMDD-YYYYMMDD, e.g., 20241201-20241227)"
            Run-Backtest -timerange $range
        }
        "4" { Analyze-Results }
        "5" { Start-PaperTrading }
        "6" { Start-LiveTrading }
        "7" { Show-Config }
        "8" { 
            Write-Host "👋 Goodbye!" -ForegroundColor Cyan
            exit 
        }
        default { 
            Write-Host "❌ Invalid option. Please try again." -ForegroundColor Red 
        }
    }
    
    if ($choice -ne "8") {
        Write-Host ""
        Write-Host "Press any key to continue..." -ForegroundColor Gray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Clear-Host
    }
} while ($choice -ne "8")
