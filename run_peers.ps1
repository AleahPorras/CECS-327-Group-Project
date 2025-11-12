$ScriptFile = "stupid.py"
$PeerCount = 4

Write-Host "Starting Peer 1 (Base)..."
# Start the first (base) peer
Start-Process python -ArgumentList $ScriptFile

# Wait 2 seconds for the base peer to initialize
Write-Host "Waiting 2 seconds for base peer..."
Start-Sleep -Seconds 2

# Start the rest of the peers
2..$PeerCount | ForEach-Object {
    Write-Host "Starting Peer $_..."
    Start-Process python -ArgumentList $ScriptFile
    Start-Sleep -Seconds 1
}

Write-Host "All peers launched."