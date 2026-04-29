param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "root",
    [string]$Password = "rootpass123",
    [string]$Input = ".\\backup.sql"
)

$env:MYSQL_PWD = $Password
Get-Content -Raw $Input | mysql -h $Host -P $Port -u $User
Remove-Item Env:MYSQL_PWD
Write-Host "Restore completed from $Input"
