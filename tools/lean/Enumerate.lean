import Lean
import Lean.OriginalConstKind

open Lean

def rawNameParts : Name → List Json
  | .anonymous => []
  | .str parentName part => rawNameParts parentName ++ [Json.mkObj [("str", toJson part)]]
  | .num parentName part => rawNameParts parentName ++ [Json.mkObj [("num", toJson part)]]

/- Enumerate original theorem declarations before any expression filtering.
   Owner modules are explicit; internal/private entries remain in the manifest. -/
def main (args : List String) : IO UInt32 := do
  let [configPath] := args | throw (IO.userError "usage: lean --run Enumerate.lean config.json")
  initSearchPath (← findSysroot)
  let config ← IO.ofExcept (Json.parse (← IO.FS.readFile configPath))
  let modules ← IO.ofExcept (config.getObjValAs? (Array String) "modules")
  let output ← IO.ofExcept (config.getObjValAs? String "output")
  let env ← importModules (modules.map fun module => {module := module.toName}) {}
  let env := env.setExporting false
  let mut declarations : Array Json := #[]
  for (name, fallback) in env.constants.toList do
    unless wasOriginallyTheorem env name do continue
    let some index := env.getModuleIdxFor? name | continue
    let owner := env.header.moduleNames[index.toNat]!.toString
    unless modules.contains owner do continue
    let info := (env.setExporting false).find? name |>.getD fallback
    declarations := declarations.push (Json.mkObj [
      ("name", toJson name.toString), ("module", toJson owner),
      ("name_parts", Json.arr (rawNameParts name).toArray),
      ("universe_parameters", toJson (info.levelParams.map Name.toString)),
      ("internal", toJson name.isInternal), ("private", toJson (isPrivateName name)),
      ("body_available", toJson ((info.value? (allowOpaque := true)).isSome))])
  let report := Json.mkObj [("format", toJson ("leanputer.declaration-population.v1" : String)),
    ("lean_version", toJson Lean.versionString), ("modules", toJson modules),
    ("declarations", Json.arr declarations)]
  IO.FS.writeFile output (report.pretty ++ "\n")
  return 0
