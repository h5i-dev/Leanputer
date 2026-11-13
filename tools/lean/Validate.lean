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
    if name == "False" && fields.size == 2 then return .const ``False []
    if name == "False.rec" && fields.size == 3 then
      return .const ``False.rec [numericLevel (← fields[2]!.getNat?)]
    throw "unsupported replay logical primitive"
  let expected := if tag == "var" || tag == "sort" || tag == "const" then 2 else 3
  if fields.size != expected then throw "malformed replay expression arity"
  match tag with
  | "var" => return .bvar (← fields[1]!.getNat?)
  | "sort" => return .sort (numericLevel (← fields[1]!.getNat?))
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
  let primitive : Lean.Declaration := .inductDecl [] 0 [{name := ``False, type := .sort .zero, ctors := []}] false
  let basis ← IO.ofExcept ((Lean.Kernel.Environment.addDecl environment.toKernelEnv {} primitive).mapError (fun _ => "Lean rejected primitive basis"))
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
