param(
  [string]$ServerHost = "124.220.228.197",
  [string]$User = "ubuntu",
  [string]$KeyPath = "$env:USERPROFILE\.ssh\txssh2.pem"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $KeyPath)) {
  throw "SSH key not found: $KeyPath"
}

$remoteCmd = "sudo sed -i 's/\r$//' /opt/gewuxueshu/scripts/update_prod_server.sh && sudo env REPO_OWNER=M-houres REPO_NAME=GWU-AD BRANCH=main bash /opt/gewuxueshu/scripts/update_prod_server.sh"
ssh -o ServerAliveInterval=20 -o ServerAliveCountMax=6 -i "$KeyPath" "$User@$ServerHost" $remoteCmd
