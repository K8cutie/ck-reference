# scripts/ps_api_helpers.ps1
function _ck-base { if ($env:BASE) { $env:BASE } else { "http://127.0.0.1:8000" } }
function _ck-headers {
  $h = @{}
  if ($env:CK_API) { $h["X-API-Key"] = $env:CK_API }
  return $h
}

function ckget {
  param([Parameter(Mandatory)][string]$Path, [hashtable]$Query=@{})
  $uri = (_ck-base) + $Path
  if ($Query.Count) { $uri += "?" + ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" } -join "&") }
  Invoke-RestMethod -Method Get -Uri $uri -Headers (_ck-headers)
}

function ckpost {
  param([Parameter(Mandatory)][string]$Path, $JsonBody=$null)
  $uri = (_ck-base) + $Path
  $headers = (_ck-headers) + @{ "Content-Type" = "application/json" }
  $body = if ($JsonBody -ne $null) { $JsonBody | ConvertTo-Json -Depth 10 } else { "{}" }
  Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body
}

# handy shortcuts
function ckreclose { param([string]$Period = (Get-Date).ToString('yyyy-MM')) ckpost "/gl/reclose/$Period" }
function ckreopen  { param([Parameter(Mandatory)][string]$Period) ckpost "/gl/reopen/$Period" }
function ckclose   { param([Parameter(Mandatory)][string]$Period, [int]$EquityId=3) ckpost "/gl/close/$Period?equity_account_id=$EquityId" }
