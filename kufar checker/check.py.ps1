$t = [IO.File]::ReadAllText("test_page.html")

# 1. NEXT_DATA present?
$idx = $t.IndexOf("__NEXT_DATA__")
Write-Host "NEXT_DATA tag found: $($idx -ge 0)"

# 2. Script tag format around it
if ($idx -ge 0) {
    Write-Host "Context: $($t.Substring([Math]::Max(0,$idx-60), 120))"
}

# 3. ads key and total
$adsIdx = $t.IndexOf('"ads":[')
Write-Host "ads array found: $($adsIdx -ge 0)"
if ($adsIdx -ge 0) {
    Write-Host "ads snippet: $($t.Substring($adsIdx, 200))"
}
$totalIdx = $t.IndexOf('"total":"')
if ($totalIdx -ge 0) { Write-Host "total: $($t.Substring($totalIdx+9, 12))" }

# 4. ad_id occurrences (real ads in SSR data?)
$adIds = [regex]::Matches($t, '"ad_id":(\d+)')
Write-Host "ad_id occurrences: $($adIds.Count)"
if ($adIds.Count -gt 0) {
    Write-Host "first: $($adIds[0].Value)"
    Write-Host "second: $($adIds[1].Value)"
}
