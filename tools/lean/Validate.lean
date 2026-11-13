import Lean

open Lean

/- Independent evaluation-only Lean kernel replay of exported JSON judgments.
   This program is never called by the weighted checker. -/
namespace LeanputerReplay

def numericLevel (n : Nat) : Level := Nat.rec .zero (fun _ level => .succ level) n

partial def expression (json : Json) : Except String Expr := do
  let fields ← json.getArr?
  if fields.isEmpty then throw "empty replay expression"
  let tag ← fields[0]!.getStr?
  if tag == "builtin" then
    let name ← fields[1]!.getStr?
    if fields.size == 2 then
      if name == "False" then return .const ``False []
      if name == "True" then return .const ``True []
      if name == "True.intro" then return .const ``True.intro []
      if name == "Or" then return .const ``Or []
      if name == "Or.inl" then return .const ``Or.inl []
      if name == "Or.inr" then return .const ``Or.inr []
      if name == "Or.rec" then return .const ``Or.rec []
      if name == "Decidable" then return .const ``Decidable []
      if name == "Decidable.isFalse" then return .const ``Decidable.isFalse []
      if name == "Decidable.isTrue" then return .const ``Decidable.isTrue []
      if name == "Bool" then return .const ``Bool []
      if name == "Bool.false" then return .const ``Bool.false []
      if name == "Bool.true" then return .const ``Bool.true []
      if name == "Nat" then return .const ``Nat []
      if name == "Nat.zero" then return .const ``Nat.zero []
      if name == "Nat.succ" then return .const ``Nat.succ []
      if name == "Iff" then return .const ``Iff []
      if name == "Iff.intro" then return .const ``Iff.intro []
      if name == "And" then return .const ``And []
      if name == "And.intro" then return .const ``And.intro []
    if fields.size == 3 then
      let level := numericLevel (← fields[2]!.getNat?)
      if name == "False.rec" then return .const ``False.rec [level]
      if name == "True.rec" then return .const ``True.rec [level]
      if name == "And.rec" then return .const ``And.rec [level]
      if name == "Iff.rec" then return .const ``Iff.rec [level]
      if name == "Nonempty" then return .const ``Nonempty [level]
      if name == "Nonempty.intro" then return .const ``Nonempty.intro [level]
      if name == "Nonempty.rec" then return .const ``Nonempty.rec [level]
      if name == "Exists" then return .const ``Exists [level]
      if name == "Exists.intro" then return .const ``Exists.intro [level]
      if name == "Exists.rec" then return .const ``Exists.rec [level]
      if name == "Quot" then return .const ``Quot [level]
      if name == "Quot.mk" then return .const ``Quot.mk [level]
      if name == "Quot.ind" then return .const ``Quot.ind [level]
      if name == "Decidable.rec" then return .const ``Decidable.rec [level]
      if name == "Subtype" then return .const ``Subtype [level]
      if name == "Subtype.mk" then return .const ``Subtype.mk [level]
      if name == "Bool.rec" then return .const ``Bool.rec [level]
      if name == "Option" then return .const ``Option [level]
      if name == "Option.none" then return .const ``Option.none [level]
      if name == "Option.some" then return .const ``Option.some [level]
      if name == "Inhabited" then return .const ``Inhabited [level]
      if name == "Inhabited.mk" then return .const ``Inhabited.mk [level]
      if name == "Mul" then return .const ``Mul [level]
      if name == "Mul.mk" then return .const ``Mul.mk [level]
      if name == "Add" then return .const ``Add [level]
      if name == "Add.mk" then return .const ``Add.mk [level]
      if name == "Subsingleton" then return .const ``Subsingleton [level]
      if name == "Subsingleton.intro" then return .const ``Subsingleton.intro [level]
      if name == "Zero" then return .const ``Zero [level]
      if name == "Zero.mk" then return .const ``Zero.mk [level]
      if name == "One" then return .const ``One [level]
      if name == "One.mk" then return .const ``One.mk [level]
      if name == "Nat.rec" then return .const ``Nat.rec [level]
      if name == "OfNat" then return .const ``OfNat [level]
      if name == "OfNat.mk" then return .const ``OfNat.mk [level]
      if name == "LT" then return .const ``LT [level]
      if name == "LT.mk" then return .const ``LT.mk [level]
      if name == "LE" then return .const ``LE [level]
      if name == "LE.mk" then return .const ``LE.mk [level]
      if name == "PUnit" then return .const ``PUnit [level]
      if name == "PUnit.unit" then return .const ``PUnit.unit [level]
    if fields.size == 3 then
      if name == "Eq" then return .const ``Eq [numericLevel (← fields[2]!.getNat?)]
      if name == "Eq.refl" then return .const ``Eq.refl [numericLevel (← fields[2]!.getNat?)]
      if name == "HEq" then return .const ``HEq [numericLevel (← fields[2]!.getNat?)]
      if name == "HEq.refl" then return .const ``HEq.refl [numericLevel (← fields[2]!.getNat?)]
    if (name == "PProd" || name == "PProd.mk" || name == "Prod" || name == "Prod.mk" || name == "Membership" || name == "Membership.mk") && fields.size == 4 then
      return .const name.toName [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    if (name == "PProd.rec" || name == "Prod.rec" || name == "Membership.rec") && fields.size == 5 then
      return .const name.toName [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?),numericLevel (← fields[4]!.getNat?)]
    if name == "HEq.rec" && fields.size == 4 then
      return .const ``HEq.rec [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    if name == "Option.rec" && fields.size == 4 then
      return .const ``Option.rec [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    if fields.size == 4 && (name == "Inhabited.rec" || name == "Mul.rec" || name == "Add.rec" || name == "Subsingleton.rec" || name == "Zero.rec" || name == "One.rec" || name == "OfNat.rec" || name == "PUnit.rec" || name == "LT.rec" || name == "LE.rec") then
      return .const name.toName [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    if name == "Subtype.rec" && fields.size == 4 then
      return .const ``Subtype.rec [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    if name == "Quot.lift" && fields.size == 4 then
      return .const ``Quot.lift [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    if name == "Eq.rec" && fields.size == 4 then
      return .const ``Eq.rec [numericLevel (← fields[2]!.getNat?),numericLevel (← fields[3]!.getNat?)]
    throw "unsupported replay logical primitive"
  if tag == "proj" && fields.size == 4 then
    let family ← fields[1]!.getStr?
    let index ← fields[2]!.getNat?
    let inner ← expression fields[3]!
    if index < 2 && (family == "Iff" || family == "And" || family == "Subtype" || family == "PProd" || family == "Prod") then
      return .proj family.toName index inner
    if index == 0 && (family == "Inhabited" || family == "Mul" || family == "Add" || family == "Subsingleton" || family == "Zero" || family == "One" || family == "OfNat" || family == "LT" || family == "LE" || family == "Membership") then
      return .proj family.toName index inner
    throw "unsupported replay projection"
  if tag == "let" && fields.size == 4 then
    return .letE `x (← expression fields[1]!) (← expression fields[2]!) (← expression fields[3]!) false
  let expected := if tag == "var" || tag == "sort" || tag == "const" || tag == "nat" then 2 else 3
  if fields.size != expected then throw "malformed replay expression arity"
  match tag with
  | "var" => return .bvar (← fields[1]!.getNat?)
  | "sort" => return .sort (numericLevel (← fields[1]!.getNat?))
  | "nat" => return .lit (.natVal (← fields[1]!.getNat?))
  | "const" => return .const (.str (.str .anonymous "_leanputer_user") (← fields[1]!.getStr?)) []
  | "pi" => return .forallE `x (← expression fields[1]!) (← expression fields[2]!) .default
  | "lam" => return .lam `x (← expression fields[1]!) (← expression fields[2]!) .default
  | "app" => return .app (← expression fields[1]!) (← expression fields[2]!)
  | _ => throw s!"unsupported replay expression {tag}"

def declaration (json : Json) : Except String Lean.Declaration := do
  let name := Name.str (.str .anonymous "_leanputer_user") (← json.getObjValAs? String "name")
  let type ← expression (← json.getObjVal? "type")
  let value ← json.getObjVal? "value"
  if value == Json.null then
    return .axiomDecl {name, levelParams := [], type, isUnsafe := false}
  let body ← expression value
  if (json.getObjValAs? Bool "opaque").toOption.getD false then
    return .opaqueDecl {name, levelParams := [], type, value := body, isUnsafe := false}
  return .defnDecl {
    name := name
    levelParams := []
    type := type
    value := body
    hints := .abbrev
    safety := .safe
  }

def replay (base : Lean.Kernel.Environment) (json : Json) : Except String Unit := do
  let mut env := base
  let entries := (json.getObjValAs? (Array Json) "environment").toOption.getD #[]
  for entry in entries do
    let decl ← declaration entry
    env ← (Lean.Kernel.Environment.addDecl env {} decl).mapError (fun _ => "Lean kernel rejected environment declaration")
  let type ← expression (← json.getObjVal? "claim")
  let value ← expression (← json.getObjVal? "term")
  let mut target := "leanputer_replay_target"
  while entries.any (fun entry => (entry.getObjValAs? String "name").toOption == some target) do
    target := target ++ "_"
  let decl : Lean.Declaration := .defnDecl {
    name := .str (.str .anonymous "_leanputer_user") target, levelParams := [], type, value,
    hints := .abbrev, safety := .safe}
  let _ ← (Lean.Kernel.Environment.addDecl env {} decl).mapError (fun _ => "Lean kernel rejected target judgment")
  return ()
end LeanputerReplay

def main (args : List String) : IO UInt32 := do
  let [input, output] := args | throw (IO.userError "usage: lean --run tools/lean/Validate.lean corpus.jsonl results.json")
  let environment ← mkEmptyEnvironment
  initSearchPath (← findSysroot)
  let standard ← importModules #[{module := `Init}] {}
  let mut basis := environment.toKernelEnv
  for name in [``False, ``Iff, ``And, ``Eq, ``True, ``Nonempty, ``Exists, ``Or, ``Decidable, ``Subtype, ``HEq, ``Bool, ``Option, ``Inhabited, ``Mul, ``Add, ``Subsingleton, ``Zero, ``One, ``Nat, ``OfNat, ``PUnit, ``LT, ``LE, ``PProd, ``Prod, ``Membership] do
    if name == ``Decidable then
      let some (.defnInfo negation) := standard.find? ``Not | throw (IO.userError "missing standard negation definition")
      basis ← IO.ofExcept ((Lean.Kernel.Environment.addDecl basis {} (.defnDecl negation)).mapError (fun _ => "Lean rejected negation definition"))
    if name == ``Membership then
      let some (.defnInfo annotation) := standard.find? ``outParam | throw (IO.userError "missing standard outParam definition")
      basis ← IO.ofExcept ((Lean.Kernel.Environment.addDecl basis {} (.defnDecl annotation)).mapError (fun _ => "Lean rejected outParam definition"))
    let some (.inductInfo info) := standard.find? name | throw (IO.userError "missing standard primitive")
    let mut ctors : List Lean.Constructor := []
    for ctor in info.ctors do
      let some constructor := standard.find? ctor | throw (IO.userError "missing standard constructor")
      ctors := ctors ++ [{name := ctor, type := constructor.type}]
    let primitive : Lean.Declaration := .inductDecl info.levelParams info.numParams [{name, type := info.type, ctors}] false
    basis ← IO.ofExcept ((Lean.Kernel.Environment.addDecl basis {} primitive).mapError (fun _ => s!"Lean rejected primitive basis {name}"))
  basis ← IO.ofExcept ((Lean.Kernel.Environment.addDecl basis {} .quotDecl).mapError (fun _ => "Lean rejected quotient basis"))
  let mut records : Array Json := #[]
  for line in (← IO.FS.readFile input).splitOn "\n" do
    if line.isEmpty then continue
    let json ← IO.ofExcept (Json.parse line)
    let name := (json.getObjValAs? String "name").toOption.getD "unnamed"
    if (json.getObjValAs? String "status").toOption == some "UNSUPPORTED" then
      records := records.push json
      continue
    let result := match LeanputerReplay.replay basis json with
      | .ok () => Json.mkObj [("name", toJson name), ("status", toJson ("ACCEPT" : String))]
      | .error message => Json.mkObj [("name", toJson name), ("status", toJson ("REJECT" : String)), ("reason", toJson message)]
    records := records.push result
  IO.FS.writeFile output ((Json.arr records).pretty ++ "\n")
  return 0
