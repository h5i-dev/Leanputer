import Lean
open Lean

/- Independent kernel replay. No code from the weighted checking path. -/
namespace LeanputerGenericReplay

def level (n : Nat) : Level := Nat.rec .zero (fun _ u => .succ u) n

def userName (s : String) : Name := Name.str `_leanputer_generic s

partial def expr (j : Json) : Except String Expr := do
  let a ← j.getArr?
  if a.isEmpty then throw "empty expression"
  let tag ← a[0]!.getStr?
  if tag == "var" && a.size == 2 then return .bvar (← a[1]!.getNat?)
  if tag == "sort" && a.size == 2 then return .sort (level (← a[1]!.getNat?))
  if tag == "const" && a.size == 2 then return .const (userName (← a[1]!.getStr?)) []
  if a.size != 3 then throw "unsupported expression"
  if tag == "app" then return .app (← expr a[1]!) (← expr a[2]!)
  if tag == "pi" then return .forallE `x (← expr a[1]!) (← expr a[2]!) .default
  if tag == "lam" then return .lam `x (← expr a[1]!) (← expr a[2]!) .default
  throw "unsupported expression"

def add (env : Lean.Kernel.Environment) (d : Lean.Declaration) : Except String Lean.Kernel.Environment :=
  (Lean.Kernel.Environment.addDecl env {} d).mapError (fun _ => "Lean kernel rejected declaration")

def replay (base : Lean.Kernel.Environment) (document : Json) : Except String Unit := do
  let entries ← document.getObjValAs? (Array Json) "environment"
  let mut env := base
  let mut i := 0
  while i < entries.size do
    let entry := entries[i]!
    let name ← entry.getObjValAs? String "name"
    let kind := (entry.getObjValAs? String "kind").toOption.getD "axiom"
    let type ← expr (← entry.getObjVal? "type")
    if kind == "inductive" then
      let count ← entry.getObjValAs? Nat "constructors"
      if i + count >= entries.size then throw "incomplete constructor block"
      let mut ctors : List Lean.Constructor := []
      for k in [:count] do
        let ctor := entries[i+1+k]!
        if (← ctor.getObjValAs? String "kind") != "constructor" ||
            (← ctor.getObjValAs? String "family") != name ||
            (← ctor.getObjValAs? Nat "index") != k then throw "constructor metadata mismatch"
        ctors := ctors ++ [{name := userName (← ctor.getObjValAs? String "name"), type := ← expr (← ctor.getObjVal? "type")}]
      env ← add env (.inductDecl [] 0 [{name := userName name, type, ctors}] false)
      i := i+count+1
    else if kind == "recursor" then
      let family ← entry.getObjValAs? String "family"
      let result ← entry.getObjValAs? Nat "level"
      let actualRecursor := Name.str (userName family) "rec"
      let some recursor := env.find? actualRecursor | throw "missing generated recursor"
      let levels := if recursor.levelParams.isEmpty then [] else [level result]
      env ← add env (.defnDecl {name := userName name, levelParams := [], type := type, value := .const actualRecursor levels, hints := .abbrev, safety := .safe})
      i := i+1
    else if kind == "constructor" then throw "orphan constructor"
    else if kind == "axiom" then
      env ← add env (.axiomDecl {name := userName name, levelParams := [], type := type, isUnsafe := false})
      i := i+1
    else
      let value ← expr (← entry.getObjVal? "value")
      if kind == "definition" then
        env ← add env (.defnDecl {name := userName name, levelParams := [], type := type, value := value, hints := .abbrev, safety := .safe})
      else if kind == "opaque" then
        env ← add env (.opaqueDecl {name := userName name, levelParams := [], type := type, value := value, isUnsafe := false})
      else throw "unknown kind"
      i := i+1
  let type ← expr (← document.getObjVal? "claim")
  let value ← expr (← document.getObjVal? "term")
  let _ ← add env (.defnDecl {name := userName "_target", levelParams := [], type := type, value := value, hints := .abbrev, safety := .safe})
  pure ()
end LeanputerGenericReplay

def main (args : List String) : IO UInt32 := do
  let [input, output] := args | throw (IO.userError "usage: ValidateGeneric.lean INPUT OUTPUT")
  let base := (← mkEmptyEnvironment).toKernelEnv
  let mut results : Array Json := #[]
  for line in (← IO.FS.readFile input).splitOn "\n" do
    if line.isEmpty then continue
    let document ← IO.ofExcept (Json.parse line)
    let name := (document.getObjValAs? String "name").toOption.getD "unnamed"
    results := results.push (match LeanputerGenericReplay.replay base document with
      | .ok () => Json.mkObj [("name", toJson name), ("status", toJson ("ACCEPT" : String))]
      | .error reason => Json.mkObj [("name", toJson name), ("status", toJson ("REJECT" : String)), ("reason", toJson reason)])
  IO.FS.writeFile output ((Json.arr results).pretty ++ "\n")
  pure 0
