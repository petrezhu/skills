param(
    [string]$ProjectPath = "",

    [string]$Query = "",

    [ValidateSet("schema", "stats", "search", "callers", "callees", "impact", "hotspots", "outdegree", "orphans", "file-symbols", "file-imports", "unresolved")]
    [string]$Recipe = "stats",

    [string]$Symbol = "",

    [string]$FilePath = "",

    [int]$Depth = 4,

    [int]$Limit = 50,

    [switch]$Json,

    [switch]$ListRecipes
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Resolve-ProjectRoot {
    param([string]$Candidate)

    if (-not [string]::IsNullOrWhiteSpace($Candidate) -and (Test-Path -LiteralPath $Candidate -PathType Container)) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    return (Get-Location).Path
}

function Escape-SqlLiteral {
    param([string]$Value)

    return $Value.Replace("'", "''")
}

function Require-Value {
    param([string]$Name, [string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required for recipe '$Recipe'."
    }
}

function Build-RecipeSql {
    param([string]$Name)

    $safeSymbol = Escape-SqlLiteral $Symbol
    $safeFile = Escape-SqlLiteral $FilePath
    $safeLimit = [Math]::Max(1, $Limit)
    $safeDepth = [Math]::Max(1, $Depth)

    switch ($Name) {
        "schema" {
            return "SELECT name, type FROM sqlite_master WHERE type IN ('table','view','index') ORDER BY type, name;"
        }
        "stats" {
            return @"
SELECT 'nodes' AS section, kind, COUNT(*) AS count FROM nodes GROUP BY kind
UNION ALL
SELECT 'edges' AS section, kind, COUNT(*) AS count FROM edges GROUP BY kind
UNION ALL
SELECT 'files' AS section, language AS kind, COUNT(*) AS count FROM files GROUP BY language
ORDER BY section, count DESC;
"@
        }
        "search" {
            Require-Value "Symbol" $Symbol
            return @"
SELECT id, kind, name, qualified_name, file_path, start_line, end_line, signature, docstring
FROM nodes
WHERE name LIKE '%$safeSymbol%'
   OR qualified_name LIKE '%$safeSymbol%'
   OR docstring LIKE '%$safeSymbol%'
   OR signature LIKE '%$safeSymbol%'
ORDER BY
  CASE WHEN name = '$safeSymbol' THEN 0 WHEN name LIKE '$safeSymbol%' THEN 1 ELSE 2 END,
  file_path,
  start_line
LIMIT $safeLimit;
"@
        }
        "callers" {
            Require-Value "Symbol" $Symbol
            return @"
SELECT caller.name, caller.kind, caller.file_path, caller.start_line, caller.end_line, e.line AS call_line
FROM edges e
JOIN nodes target ON e.target = target.id
JOIN nodes caller ON e.source = caller.id
WHERE e.kind = 'calls'
  AND (target.name = '$safeSymbol' OR target.qualified_name = '$safeSymbol')
ORDER BY caller.file_path, caller.start_line
LIMIT $safeLimit;
"@
        }
        "callees" {
            Require-Value "Symbol" $Symbol
            return @"
SELECT callee.name, callee.kind, callee.file_path, callee.start_line, callee.end_line, e.line AS call_line
FROM edges e
JOIN nodes source ON e.source = source.id
JOIN nodes callee ON e.target = callee.id
WHERE e.kind = 'calls'
  AND (source.name = '$safeSymbol' OR source.qualified_name = '$safeSymbol')
ORDER BY callee.file_path, callee.start_line
LIMIT $safeLimit;
"@
        }
        "impact" {
            Require-Value "Symbol" $Symbol
            return @"
WITH RECURSIVE upstream(id, name, kind, file_path, start_line, end_line, depth, relationship) AS (
  SELECT caller.id, caller.name, caller.kind, caller.file_path, caller.start_line, caller.end_line, 1, e.kind
  FROM edges e
  JOIN nodes target ON e.target = target.id
  JOIN nodes caller ON e.source = caller.id
  WHERE e.kind IN ('calls', 'references', 'imports')
    AND (target.name = '$safeSymbol' OR target.qualified_name = '$safeSymbol')
  UNION ALL
  SELECT caller.id, caller.name, caller.kind, caller.file_path, caller.start_line, caller.end_line, upstream.depth + 1, e.kind
  FROM upstream
  JOIN edges e ON e.target = upstream.id AND e.kind IN ('calls', 'references', 'imports')
  JOIN nodes caller ON e.source = caller.id
  WHERE upstream.depth < $safeDepth
)
SELECT DISTINCT name, kind, file_path, start_line, end_line, depth, relationship
FROM upstream
ORDER BY depth, relationship, file_path, start_line
LIMIT $safeLimit;
"@
        }
        "hotspots" {
            return @"
SELECT target.name, target.kind, target.file_path, target.start_line, COUNT(*) AS incoming_calls
FROM edges e
JOIN nodes target ON e.target = target.id
WHERE e.kind = 'calls'
  AND target.kind IN ('function', 'method')
GROUP BY target.id
ORDER BY incoming_calls DESC, target.file_path
LIMIT $safeLimit;
"@
        }
        "outdegree" {
            return @"
SELECT source.name, source.kind, source.file_path, source.start_line, COUNT(DISTINCT e.target) AS outgoing_calls
FROM edges e
JOIN nodes source ON e.source = source.id
WHERE e.kind = 'calls'
  AND source.kind IN ('function', 'method')
GROUP BY source.id
ORDER BY outgoing_calls DESC, source.file_path
LIMIT $safeLimit;
"@
        }
        "orphans" {
            return @"
SELECT n.name, n.kind, n.file_path, n.start_line, n.end_line
FROM nodes n
WHERE n.kind IN ('function', 'method')
  AND COALESCE(n.is_exported, 0) = 0
  AND n.id NOT IN (SELECT target FROM edges WHERE kind = 'calls')
ORDER BY n.file_path, n.start_line
LIMIT $safeLimit;
"@
        }
        "file-symbols" {
            Require-Value "FilePath" $FilePath
            return @"
SELECT kind, name, qualified_name, start_line, end_line, signature, docstring
FROM nodes
WHERE file_path = '$safeFile'
  AND kind IN ('class', 'interface', 'struct', 'enum', 'function', 'method', 'property', 'field')
ORDER BY start_line, kind
LIMIT $safeLimit;
"@
        }
        "file-imports" {
            Require-Value "FilePath" $FilePath
            return @"
SELECT imported.name, imported.kind, imported.file_path, imported.start_line
FROM edges e
JOIN nodes source ON e.source = source.id
JOIN nodes imported ON e.target = imported.id
WHERE e.kind = 'imports'
  AND source.file_path = '$safeFile'
ORDER BY imported.file_path, imported.name
LIMIT $safeLimit;
"@
        }
        "unresolved" {
            if ([string]::IsNullOrWhiteSpace($FilePath)) {
                return "SELECT reference_name, reference_kind, file_path, line, col, candidates FROM unresolved_refs ORDER BY file_path, line LIMIT $safeLimit;"
            }

            return "SELECT reference_name, reference_kind, file_path, line, col, candidates FROM unresolved_refs WHERE file_path = '$safeFile' ORDER BY line LIMIT $safeLimit;"
        }
    }
}

if ($ListRecipes) {
    @(
        "schema",
        "stats",
        "search -Symbol <text>",
        "callers -Symbol <name>",
        "callees -Symbol <name>",
        "impact -Symbol <name> [-Depth 4]",
        "hotspots",
        "outdegree",
        "orphans",
        "file-symbols -FilePath <relative/path.cs>",
        "file-imports -FilePath <relative/path.cs>",
        "unresolved [-FilePath <relative/path.cs>]"
    ) | ForEach-Object { Write-Host $_ }
    exit 0
}

$root = Resolve-ProjectRoot $ProjectPath
$dbPath = Join-Path $root ".codegraph\codegraph.db"
if (-not (Test-Path -LiteralPath $dbPath -PathType Leaf)) {
    throw "CodeGraph database not found: $dbPath"
}

$sql = if ([string]::IsNullOrWhiteSpace($Query)) { Build-RecipeSql $Recipe } else { $Query }

$env:CODEGRAPH_DB = $dbPath
$env:CODEGRAPH_SQL = $sql
$env:CODEGRAPH_JSON = if ($Json) { "1" } else { "0" }

@'
import json
import os
import sqlite3

db_path = os.environ["CODEGRAPH_DB"]
sql = os.environ["CODEGRAPH_SQL"]
as_json = os.environ.get("CODEGRAPH_JSON") == "1"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(sql).fetchall()
finally:
    conn.close()

records = [dict(row) for row in rows]
if as_json:
    print(json.dumps(records, ensure_ascii=False, indent=2))
else:
    if not records:
        print("(no rows)")
    else:
        columns = list(records[0].keys())
        print(" | ".join(columns))
        print(" | ".join(["---"] * len(columns)))
        for record in records:
            print(" | ".join("" if record[column] is None else str(record[column]).replace("\r", " ").replace("\n", " ") for column in columns))
'@ | python -
