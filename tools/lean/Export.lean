import Lean
import Lean.OriginalConstKind

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
  | .sort level => return jsonArray [text "sort", toJson (← groundLevel level)]
  | .forallE _ domain body _ =>
    return jsonArray [text "pi", ← encodeExpr env domain, ← encodeExpr env body]
  | .lam _ domain body _ =>
    return jsonArray [text "lam", ← encodeExpr env domain, ← encodeExpr env body]
  | .app fn arg => return jsonArray [text "app", ← encodeExpr env fn, ← encodeExpr env arg]
  | .const name levels =>
    let values ← levels.mapM (fun level => (liftM (groundLevel level) : ExportM Nat))
    if (name == ``False || name == ``Iff || name == ``Iff.intro || name == ``And || name == ``And.intro || name == ``True || name == ``True.intro || name == ``Or || name == ``Or.inl || name == ``Or.inr || name == ``Or.rec || name == ``Decidable || name == ``Decidable.isFalse || name == ``Decidable.isTrue || name == ``Bool || name == ``Bool.false || name == ``Bool.true || name == ``Nat || name == ``Nat.zero || name == ``Nat.succ) && values.isEmpty then
      return jsonArray [text "builtin",text name.toString]
    if (name == ``False.rec || name == ``True.rec || name == ``And.rec || name == ``Iff.rec ||
        name == ``Nonempty || name == ``Nonempty.intro || name == ``Nonempty.rec ||
        name == ``Exists || name == ``Exists.intro || name == ``Exists.rec ||
        name == ``Quot || name == ``Quot.mk || name == ``Quot.ind || name == ``Decidable.rec ||
        name == ``Subtype || name == ``Subtype.mk || name == ``Bool.rec ||
        name == ``Option || name == ``Option.none || name == ``Option.some ||
        name == ``Inhabited || name == ``Inhabited.mk || name == ``Mul || name == ``Mul.mk ||
        name == ``Add || name == ``Add.mk || name == ``Subsingleton || name == ``Subsingleton.intro ||
        name == ``Zero || name == ``Zero.mk || name == ``One || name == ``One.mk || name == ``Nat.rec || name == ``OfNat || name == ``OfNat.mk ||
        name == ``PUnit || name == ``PUnit.unit || name == ``LT || name == ``LT.mk || name == ``LE || name == ``LE.mk) && values.length == 1 then
      return jsonArray [text "builtin",text name.toString,toJson values[0]!]
    if (name == ``Eq || name == ``Eq.refl || name == ``HEq || name == ``HEq.refl) && values.length == 1 then
      return jsonArray [text "builtin",text name.toString,toJson values[0]!]
    if (name == ``Eq.rec || name == ``Quot.lift || name == ``Subtype.rec || name == ``HEq.rec || name == ``Option.rec ||
        name == ``Inhabited.rec || name == ``Mul.rec || name == ``Add.rec || name == ``Subsingleton.rec || name == ``Zero.rec || name == ``One.rec || name == ``OfNat.rec || name == ``PUnit.rec || name == ``LT.rec || name == ``LE.rec || name == ``PProd || name == ``PProd.mk || name == ``Prod || name == ``Prod.mk || name == ``Membership || name == ``Membership.mk) && values.length == 2 then
      return jsonArray [text "builtin",text name.toString,toJson values[0]!,toJson values[1]!]
    if (name == ``PProd.rec || name == ``Prod.rec || name == ``Membership.rec || name == ``HAdd || name == ``HAdd.mk || name == ``HMul || name == ``HMul.mk) && values.length == 3 then
      return jsonArray [text "builtin",text name.toString,toJson values[0]!,toJson values[1]!,toJson values[2]!]
    if (name == ``HAdd.rec || name == ``HMul.rec) && values.length == 4 then
      return jsonArray [text "builtin",text name.toString,toJson values[0]!,toJson values[1]!,toJson values[2]!,toJson values[3]!]
    let specialized ← ensureDeclaration env name values
    return jsonArray [text "const", text specialized]
  | .mdata _ inner => encodeExpr env inner
  | .letE _ type value body _ =>
    return jsonArray [text "let", ← encodeExpr env type, ← encodeExpr env value, ← encodeExpr env body]
  | .proj name index inner =>
    if (name == ``Iff || name == ``And || name == ``Subtype || name == ``PProd || name == ``Prod) && index < 2 then
      return jsonArray [text "proj",text name.toString,toJson index,← encodeExpr env inner]
    if (name == ``Inhabited || name == ``Mul || name == ``Add || name == ``Subsingleton || name == ``Zero || name == ``One || name == ``OfNat || name == ``LT || name == ``LE || name == ``Membership || name == ``HAdd || name == ``HMul) && index == 0 then
      return jsonArray [text "proj",text name.toString,toJson index,← encodeExpr env inner]
    throw s!"unsupported structure projection {name}.{index}"
  | .lit (.natVal value) => return jsonArray [text "nat",toJson value]
  | .lit .. => throw "unsupported literal"
  | .fvar .. => throw "unsupported free variable"
  | .mvar .. => throw "unsupported expression metavariable"

partial def ensureDeclaration (env : Environment) (name : Name) (levels : List Nat) : ExportM String := do
  let specialized := key name levels
  if (← get).complete.contains specialized then return specialized
  if (← get).visiting.contains specialized then throw s!"unsupported cyclic dependency {specialized}"
  let some info := (env.setExporting false).find? name | throw s!"unknown constant {name}"
  if info.isUnsafe || info.isPartial then throw s!"unsupported unsafe/partial declaration {name}"
  if info.levelParams.length != levels.length then throw s!"universe arity mismatch for {name}"
  let (value?, isOpaque) ← match info with
    | .axiomInfo _ =>
      if (getOriginalConstKind? env name).any (· == .axiom) then pure (none, false)
      else throw s!"unsupported unavailable body for non-axiom dependency {name}"
    | .defnInfo value => pure (some value.value, false)
    | .thmInfo value => pure (some value.value, true)
    | .opaqueInfo value => pure (some value.value, true)
    | _ => throw s!"unsupported inductive/constructor/recursor/quotient dependency {name}"
  modify fun state => { state with visiting := state.visiting.insert specialized }
  let instantiate := fun expr => expr.instantiateLevelParams info.levelParams (levels.map numericLevel)
  let type ← encodeExpr env (instantiate info.type)
  let value ← match value? with
    | none => pure Json.null
    | some expr => encodeExpr env (instantiate expr)
  let declaration := Json.mkObj [("name", text specialized), ("type", type), ("value", value), ("opaque", toJson isOpaque)]
  modify fun state => { state with
    declarations := state.declarations.push declaration
    complete := state.complete.insert specialized
    visiting := state.visiting.erase specialized }
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
    ("format", text "leanputer.dependent.v1"),
    ("name", text (key name levels)),
    ("term", term), ("claim", claim),
    ("environment", Json.arr state.declarations),
    ("provenance", Json.mkObj [("lean_version", text Lean.versionString),
      ("source_constant", text name.toString), ("ground_levels", toJson levels),
      ("source_name_parts", Json.arr (nameParts name).toArray),
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
    let nativeName ← match (target.getObjValAs? (Array Json) "name_parts").toOption with
      | some parts => IO.ofExcept (decodeName parts)
      | none => pure name.toName
    let levels := (target.getObjValAs? (List Nat) "levels").toOption.getD []
    let record := match exportTarget env nativeName levels with
      | .ok document => document
      | .error reason => Json.mkObj [("format", text "leanputer.dependent.v1"),
          ("name", text (key nativeName levels)), ("status", text "UNSUPPORTED"), ("reason", text reason),
          ("provenance", Json.mkObj [("source_constant", text name), ("source_name_parts", Json.arr (nameParts nativeName).toArray),
              ("ground_levels", toJson levels), ("lean_version", text Lean.versionString)])]
    results := results.push record.compress
  IO.FS.writeFile output (String.intercalate "\n" results.toList ++ "\n")
  return 0
