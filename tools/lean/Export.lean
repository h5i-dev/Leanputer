import Lean

open Lean

/- Syntax-only elaborated-expression exporter. No inferType, whnf, isDefEq,
   kernel answer, certificate generation, or reduction is performed here. -/
namespace LeanputerExport

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

def key (name : Name) (levels : List Nat) : String :=
  name.toString ++ "@[" ++ String.intercalate "," (levels.map toString) ++ "]"

structure ExportState where
  declarations : Array Json := #[]
  complete : Std.HashSet String := {}
  visiting : Std.HashSet String := {}

abbrev ExportM := StateT ExportState (Except String)

mutual
partial def encodeExpr (env : Environment) (expr : Expr) : ExportM Json := do
  match expr with
  | .bvar index => return jsonArray [text "var", toJson index]
  | .sort level => return jsonArray [text "sort", toJson (← groundLevel level)]
  | .forallE _ domain body _ =>
    return jsonArray [text "pi", ← encodeExpr env domain, ← encodeExpr env body]
  | .lam _ domain body _ =>
    return jsonArray [text "lam", ← encodeExpr env domain, ← encodeExpr env body]
  | .app fn arg => return jsonArray [text "app", ← encodeExpr env fn, ← encodeExpr env arg]
  | .const name levels =>
    let values ← levels.mapM (fun level => (liftM (groundLevel level) : ExportM Nat))
    let specialized ← ensureDeclaration env name values
    return jsonArray [text "const", text specialized]
  | .mdata _ inner => encodeExpr env inner
  | .letE .. => throw "unsupported let expression (no external zeta reduction)"
  | .proj .. => throw "unsupported structure projection"
  | .lit .. => throw "unsupported literal"
  | .fvar .. => throw "unsupported free variable"
  | .mvar .. => throw "unsupported expression metavariable"

partial def ensureDeclaration (env : Environment) (name : Name) (levels : List Nat) : ExportM String := do
  let specialized := key name levels
  if (← get).complete.contains specialized then return specialized
  if (← get).visiting.contains specialized then throw s!"unsupported cyclic dependency {specialized}"
  let some info := env.find? name | throw s!"unknown constant {name}"
  if info.isUnsafe || info.isPartial then throw s!"unsupported unsafe/partial declaration {name}"
  if info.levelParams.length != levels.length then throw s!"universe arity mismatch for {name}"
  let value? ← match info with
    | .axiomInfo _ => pure none
    | .defnInfo value => pure (some value.value)
    | .thmInfo _ => throw s!"unsupported opaque theorem dependency {name}"
    | .opaqueInfo _ => throw s!"unsupported opaque dependency {name}"
    | _ => throw s!"unsupported inductive/constructor/recursor/quotient dependency {name}"
  modify fun state => { state with visiting := state.visiting.insert specialized }
  let instantiate := fun expr => expr.instantiateLevelParams info.levelParams (levels.map numericLevel)
  let type ← encodeExpr env (instantiate info.type)
  let value ← match value? with
    | none => pure Json.null
    | some expr => encodeExpr env (instantiate expr)
  let declaration := Json.mkObj [("name", text specialized), ("type", type), ("value", value)]
  modify fun state => { state with
    declarations := state.declarations.push declaration
    complete := state.complete.insert specialized
    visiting := state.visiting.erase specialized }
  return specialized
end

def exportTarget (env : Environment) (name : Name) (levels : List Nat) : Except String Json := do
  let some info := env.find? name | throw s!"unknown target {name}"
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
    ("format", text "leanputer.dependent.v1"),
    ("name", text (key name levels)),
    ("term", term), ("claim", claim),
    ("environment", Json.arr state.declarations),
    ("provenance", Json.mkObj [("lean_version", text Lean.versionString),
      ("source_constant", text name.toString), ("ground_levels", toJson levels),
      ("preparation", text "syntax-only Expr traversal and universe instantiation")])]

end LeanputerExport

open LeanputerExport

def main (args : List String) : IO UInt32 := do
  let [configPath] := args | throw (IO.userError "usage: lean --run tools/lean/Export.lean config.json")
  initSearchPath (← findSysroot)
  let config ← IO.ofExcept (Json.parse (← IO.FS.readFile configPath))
  let modules ← IO.ofExcept (config.getObjValAs? (Array String) "modules")
  let targets ← IO.ofExcept (config.getObjValAs? (Array Json) "targets")
  let output ← IO.ofExcept (config.getObjValAs? String "output")
  let env ← importModules (modules.map fun name => { module := name.toName }) {}
  let mut results : Array String := #[]
  for target in targets do
    let name ← IO.ofExcept (target.getObjValAs? String "name")
    let levels := (target.getObjValAs? (List Nat) "levels").toOption.getD []
    let record := match exportTarget env name.toName levels with
      | .ok document => document
      | .error reason => Json.mkObj [("format", text "leanputer.dependent.v1"),
          ("name", text name), ("status", text "UNSUPPORTED"), ("reason", text reason)]
    results := results.push record.compress
  IO.FS.writeFile output (String.intercalate "\n" results.toList ++ "\n")
  return 0
