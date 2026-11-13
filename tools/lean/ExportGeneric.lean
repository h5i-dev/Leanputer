import Lean
import Lean.OriginalConstKind

open Lean

/- Syntax-only elaborated-expression exporter. No inferType, whnf, isDefEq,
   kernel answer, certificate generation, or reduction is performed here. -/
namespace LeanputerGenericExport

def jsonArray (items : List Json) : Json := Json.arr items.toArray
def text (value : String) : Json := toJson value

partial def groundLevel : Level → Except String Nat
  | .zero => pure 0
  | .succ level => return (← groundLevel level) + 1
  | .max left right => return max (← groundLevel left) (← groundLevel right)
  | .imax left right => do
    let a ← groundLevel left
    let b ← groundLevel right
    return if b == 0 then 0 else max a b
  | .param name => throw s!"unsupported unresolved universe parameter {name}"
  | .mvar _ => throw "unsupported universe metavariable"

def numericLevel (n : Nat) : Level := Nat.rec .zero (fun _ level => .succ level) n

def nameParts : Name → List Json
  | .anonymous => []
  | .str parentName part => nameParts parentName ++ [Json.mkObj [("str", toJson part)]]
  | .num parentName part => nameParts parentName ++ [Json.mkObj [("num", toJson part)]]

def decodeName (parts : Array Json) : Except String Name :=
  parts.foldlM (fun parentName part => do
    match (part.getObjValAs? String "str").toOption with
    | some text => return .str parentName text
    | none => return .num parentName (← part.getObjValAs? Nat "num")) .anonymous

def key (name : Name) (levels : List Nat) : String :=
  let base := if name.toString.toName == name then name.toString
              else "encoded:" ++ (Json.arr (nameParts name).toArray).compress
  base ++ "@[" ++ String.intercalate "," (levels.map toString) ++ "]"

structure ExportState where
  declarations : Array Json := #[]
  complete : Std.HashSet String := {}
  visiting : Std.HashSet String := {}

abbrev ExportM := StateT ExportState (Except String)

mutual
partial def encodeExpr (env : Environment) (expr : Expr) : ExportM Json := do
  match expr with
  | .bvar index => return jsonArray [text "var", toJson index]
  | .sort u => return jsonArray [text "sort", toJson (← groundLevel u)]
  | .forallE _ domain body _ => return jsonArray [text "pi", ← encodeExpr env domain, ← encodeExpr env body]
  | .lam _ domain body _ => return jsonArray [text "lam", ← encodeExpr env domain, ← encodeExpr env body]
  | .app fn arg => return jsonArray [text "app", ← encodeExpr env fn, ← encodeExpr env arg]
  | .const name levels =>
    let values ← levels.mapM (fun u => (liftM (groundLevel u) : ExportM Nat))
    return jsonArray [text "const", text (← ensureDeclaration env name values)]
  | .mdata _ inner => encodeExpr env inner
  | .letE .. => throw "unsupported generic let expression"
  | .proj .. => throw "unsupported generic projection"
  | .lit .. => throw "unsupported generic literal"
  | .fvar .. => throw "unsupported free variable"
  | .mvar .. => throw "unsupported metavariable"

partial def ensureDeclaration (env : Environment) (name : Name) (levels : List Nat) : ExportM String := do
  let specialized := key name levels
  if (← get).complete.contains specialized then return specialized
  if (← get).visiting.contains specialized then throw s!"unsupported cyclic dependency {specialized}"
  let some info := (env.setExporting false).find? name | throw s!"unknown constant {name}"
  if info.isUnsafe || info.isPartial then throw s!"unsupported unsafe/partial declaration {name}"
  if info.levelParams.length != levels.length then throw s!"universe arity mismatch {name}"
  let instantiate := fun e => e.instantiateLevelParams info.levelParams (levels.map numericLevel)
  modify fun s => {s with visiting := s.visiting.insert specialized}
  match info with
  | .inductInfo family =>
    if !levels.isEmpty || family.all.length != 1 || family.numNested != 0 then
      throw "unsupported polymorphic/mutual/nested family export"
    let ty ← encodeExpr env family.type
    -- Resolve syntax references while building a single contiguous family block.
    -- Admission is deferred entirely to the weighted checker.
    modify fun s => {s with complete := (family.ctors.foldl (fun a c => a.insert (key c [])) s.complete).insert specialized}
    let mut ctors : Array Json := #[]
    for ctor in family.ctors do
      let some (.ctorInfo c) := (env.setExporting false).find? ctor | throw "missing constructor syntax"
      let cty ← encodeExpr env c.type
      ctors := ctors.push (Json.mkObj [("kind",text "constructor"),("name",text (key ctor [])),
        ("family",text specialized),("index",toJson c.cidx),("type",cty)])
    let header := Json.mkObj [("kind",text "inductive"),("name",text specialized),("type",ty),
      ("constructors",toJson ctors.size)]
    modify fun s => {s with declarations := s.declarations ++ #[header] ++ ctors, visiting := s.visiting.erase specialized}
  | .ctorInfo ctor =>
    let _ ← ensureDeclaration env ctor.induct levels
    modify fun s => {s with visiting := s.visiting.erase specialized}
  | .recInfo recursor =>
    if recursor.all.length != 1 || levels.length != 1 then throw "unsupported recursor universe/family shape"
    let family ← ensureDeclaration env recursor.all[0]! []
    let ty ← encodeExpr env (instantiate info.type)
    let row := Json.mkObj [("kind",text "recursor"),("name",text specialized),("type",ty),
      ("family",text family),("level",toJson levels[0]!)]
    modify fun s => {s with declarations := s.declarations.push row, complete := s.complete.insert specialized, visiting := s.visiting.erase specialized}
  | _ =>
    let (value?, kind) ← match info with
      | .axiomInfo _ =>
        if (getOriginalConstKind? env name).any (· == .axiom) then pure (none,"axiom")
        else throw s!"unavailable non-axiom body {name}"
      | .defnInfo d => pure (some d.value,"definition")
      | .thmInfo d => pure (some d.value,"opaque")
      | .opaqueInfo d => pure (some d.value,"opaque")
      | _ => throw s!"unsupported constant kind {name}"
    let ty ← encodeExpr env (instantiate info.type)
    let value ← match value? with
      | none => pure Json.null
      | some e => encodeExpr env (instantiate e)
    let row := Json.mkObj [("name",text specialized),("kind",text kind),("type",ty),("value",value)]
    modify fun s => {s with declarations := s.declarations.push row, complete := s.complete.insert specialized, visiting := s.visiting.erase specialized}
  return specialized
end

def exportTarget (env : Environment) (name : Name) (levels : List Nat) : Except String Json := do
  let some info := (env.setExporting false).find? name | throw s!"unknown target {name}"
  if info.isUnsafe || info.isPartial then throw "unsupported unsafe/partial target"
  let some value := info.value? (allowOpaque := true) | throw "target has no available proof/value"
  if info.levelParams.length != levels.length then throw "target universe arity mismatch"
  let instantiate := fun expr => expr.instantiateLevelParams info.levelParams (levels.map numericLevel)
  let action : ExportM (Json × Json) := do
    let term ← encodeExpr env (instantiate value)
    let claim ← encodeExpr env (instantiate info.type)
    return (term, claim)
  let ((term, claim), state) ← action.run {}
  return Json.mkObj [
    ("format", text "leanputer.generic.v1"),
    ("name", text (key name levels)),
    ("term", term), ("claim", claim),
    ("environment", Json.arr state.declarations),
    ("provenance", Json.mkObj [("lean_version", text Lean.versionString),
      ("source_constant", text name.toString), ("ground_levels", toJson levels),
      ("source_name_parts", Json.arr (nameParts name).toArray),
      ("preparation", text "syntax-only Expr traversal and universe instantiation")])]

end LeanputerGenericExport

open LeanputerGenericExport

def main (args : List String) : IO UInt32 := do
  let [configPath] := args | throw (IO.userError "usage: lean --run tools/lean/ExportGeneric.lean config.json")
  initSearchPath (← findSysroot)
  let config ← IO.ofExcept (Json.parse (← IO.FS.readFile configPath))
  let modules ← IO.ofExcept (config.getObjValAs? (Array String) "modules")
  let targets ← IO.ofExcept (config.getObjValAs? (Array Json) "targets")
  let output ← IO.ofExcept (config.getObjValAs? String "output")
  let env ← importModules (modules.map fun name => { module := name.toName }) {}
  let mut results : Array String := #[]
  for target in targets do
    let name ← IO.ofExcept (target.getObjValAs? String "name")
    let nativeName ← match (target.getObjValAs? (Array Json) "name_parts").toOption with
      | some parts => IO.ofExcept (decodeName parts)
      | none => pure name.toName
    let levels := (target.getObjValAs? (List Nat) "levels").toOption.getD []
    let record := match exportTarget env nativeName levels with
      | .ok document => document
      | .error reason => Json.mkObj [("format", text "leanputer.generic.v1"),
          ("name", text (key nativeName levels)), ("status", text "UNSUPPORTED"), ("reason", text reason),
          ("provenance", Json.mkObj [("source_constant", text name), ("source_name_parts", Json.arr (nameParts nativeName).toArray),
              ("ground_levels", toJson levels), ("lean_version", text Lean.versionString)])]
    results := results.push record.compress
  IO.FS.writeFile output (String.intercalate "\n" results.toList ++ "\n")
  return 0
