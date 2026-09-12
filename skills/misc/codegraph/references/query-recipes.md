# CodeGraph Query Recipes

Use these recipes when CodeGraph MCP tools are not available in the current session or when a custom SQL slice is faster than repeated file reads.

Prefer MCP tools when available:

- `codegraph_search` for symbol lookup.
- `codegraph_context` for task-focused context.
- `codegraph_callers` and `codegraph_callees` for direct call relationships.
- `codegraph_impact` for broad change impact.
- `codegraph_status` for index health.

Use the SQL fallback through:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe stats
```

## Schema

Core tables:

- `nodes`: code symbols and files. Important columns: `id`, `kind`, `name`, `qualified_name`, `file_path`, `start_line`, `end_line`, `docstring`, `signature`, `visibility`, `is_exported`, `is_async`, `is_static`.
- `edges`: graph relationships. Important columns: `source`, `target`, `kind`, `line`, `col`, `metadata`, `provenance`.
- `files`: indexed file metadata.
- `nodes_fts`: FTS5 table for searchable symbol text.
- `unresolved_refs`: references the parser could not resolve.

Common node kinds in C# projects include `file`, `class`, `interface`, `struct`, `enum`, `enum_member`, `field`, `property`, `method`, and `import`.

Common edge kinds include `contains`, `calls`, `references`, `imports`, `instantiates`, `implements`, and `extends`.

## Ready-Made Recipes

List recipes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -ListRecipes
```

Project statistics:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe stats
```

Search names, qualified names, docstrings, and signatures:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe search -Symbol FloorManagementService -Json
```

Direct callers:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe callers -Symbol SaveFloors
```

Direct callees:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe callees -Symbol SaveFloors
```

Recursive impact:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe impact -Symbol SaveFloors -Depth 4 -Limit 100
```

Most-called methods/functions:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe hotspots -Limit 20
```

Methods/functions with the most outgoing calls:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe outdegree -Limit 20
```

Potential orphan methods/functions:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe orphans -Limit 100
```

Symbols in a file:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe file-symbols -FilePath "Services/Floor/FloorManagementService.cs"
```

Unresolved references:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe unresolved
```

## Interpretation Rules

- `calls`: source node calls target node.
- `references`: source node references target node, often through type usage or symbol access.
- `imports`: source import node/file imports target.
- `contains`: file/class contains symbol.
- `instantiates`: source node constructs target type.
- `implements`: source type implements target interface.
- `extends`: source type extends target type.

## C# Notes

- Prefer `method` over `function` in C# projects.
- Constructors can appear as `method` nodes with the class name.
- A private helper that appears in `orphans` is not automatically dead code; verify event handlers, reflection, XAML bindings, Revit external commands, and generated-code entry points before deleting.
- Use `file-symbols` before editing large files to understand local structure without reading the entire file.

## Custom SQL

Run a custom query:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Query "SELECT kind, COUNT(*) AS count FROM nodes GROUP BY kind ORDER BY count DESC;" -Json
```

Keep recursive CTE depth bounded and always filter `edges.kind` for performance.
