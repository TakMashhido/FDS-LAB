# run_demo.ps1

# Stop on any error
$ErrorActionPreference = 'Stop'

# Color helper
function Write-Colored {
    param(
        [string]$Text,
        [ConsoleColor]$Color = 'White'
    )
    $orig = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = $Color
    Write-Host $Text
    $Host.UI.RawUI.ForegroundColor = $orig
}

# Step 1
Write-Colored "1) Spinning up 3-node etcd cluster…" Blue
docker-compose up -d

# Step 2
Write-Colored "2) Waiting for leader election (10s)…" Blue
Start-Sleep -Seconds 10

# Step 3
Write-Colored "3) Checking cluster status:" Blue
docker exec etcd1 etcdctl --endpoints=http://etcd1:2379 endpoint status --write-out=table
docker exec etcd2 etcdctl --endpoints=http://etcd2:2379 endpoint status --write-out=table
docker exec etcd3 etcdctl --endpoints=http://etcd3:2379 endpoint status --write-out=table

# Step 4
Write-Colored "`n4) Running Python client: writes & reads" Blue
python demo_client.py

# Step 5
Write-Colored "`n5) Which etcd node should we kill?" Blue
Write-Colored "   Available containers: etcd1, etcd2, etcd3" White
do {
    $TARGET = Read-Host "   Enter container name to kill"
    if (-not $TARGET) {
        Write-Colored "   You must enter a container name!" Red
    }
} until ($TARGET)

Write-Colored "   Killing container $TARGET…" Blue
docker kill $TARGET
Write-Colored "   $TARGET has been killed." Green

# Step 6: Wait for re-election
Write-Colored "`n6) Waiting for leader re-election after killing $TARGET (10s)…" Blue
Start-Sleep -Seconds 10

# Step 7: Re-run client
Write-Colored "`n7) Rerunning Python client to prove failover…" Blue
python demo_client.py

# Step 8: Tail logs (press Ctrl+C to stop)
Write-Colored "`n8) Tailing etcd logs (Ctrl+C to stop)…" Blue
Write-Colored "— etcd1 —" Green
Start-Process -NoNewWindow -FilePath docker -ArgumentList "logs -f etcd1"
Write-Colored "— etcd2 —" Green
Start-Process -NoNewWindow -FilePath docker -ArgumentList "logs -f etcd2"
Write-Colored "— etcd3 —" Green
Start-Process -NoNewWindow -FilePath docker -ArgumentList "logs -f etcd3"

# Keep script alive until user interrupts
while ($true) { Start-Sleep -Seconds 1 }
