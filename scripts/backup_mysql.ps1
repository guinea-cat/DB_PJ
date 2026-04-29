param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 3306,
    [string]$Database = "FlightTicketingDB",
    [string]$User = "root",
    [string]$Password = "rootpass123",
    [string]$Output = ".\\backup.sql"
)

$env:MYSQL_PWD = $Password
mysqldump -h $Host -P $Port -u $User --databases $Database --routines --triggers --single-transaction > $Output
Remove-Item Env:MYSQL_PWD
Write-Host "Backup saved to $Output"
