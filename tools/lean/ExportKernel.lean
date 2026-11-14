import Lean
import Lean.OriginalConstKind

open Lean

/- Original-scheme SYNTAX export. No inferType/whnf/isDefEq, universe grounding,
   reduction, admission answers, generated rule answers, or external checker.
   Inductive groups/constructor signatures are raw data. Recursor types are
   claims; the target checker must generate and compare them itself. -/
namespace LeanputerKernelExport

def arr (items : List Json) : Json := toJson items
def text (s : String) : Json := toJson s

def nameParts : Name → List Json
  | .anonymous => []
  | .str parent part => nameParts parent ++ [Json.mkObj [("str", text part)]]
  | .num parent part => nameParts parent ++ [Json.mkObj [("num", toJson part)]]

def name (n : Name) : Json := arr (nameParts n)
def uparams (ns : List Name) : Json := arr (ns.map name)

def decodeName (parts : Array Json) : Except String Name :=
  parts.foldlM (fun parent part => do
    match (part.getObjValAs? String "str").toOption with
    | some s => return .str parent s
    | none => return .num parent (← part.getObjValAs? Nat "num")) .anonymous

partial def level : Level → Except String Json
  | .zero => return arr [text "zero"]
  | .succ u => return arr [text "succ", ← level u]
  | .max u v => return arr [text "max", ← level u, ← level v]
  | .imax u v => return arr [text "imax", ← level u, ← level v]
  | .param p => return arr [text "param", name p]
  | .mvar _ => throw "invalid unresolved universe metavariable"

def binderInfo : BinderInfo → Nat
  | .default => 0
  | .implicit => 1
  | .strictImplicit => 2
  | .instImplicit => 3

structure ExportState where
  declarations : Array Json := #[]
  complete : Std.HashSet Name := {}
  visiting : Std.HashSet Name := {}

abbrev ExportM := StateT ExportState (Except String)

def findInfo (env : Environment) (n : Name) : Except String ConstantInfo := do
  let some info := (env.setExporting false).find? n | throw s!"unknown declaration {n}"
  if info.isUnsafe || info.isPartial then throw s!"unsupported unsafe/partial declaration {n}"
  return info

mutual
partial def expr (env : Environment) (e : Expr) : ExportM Json := do
  match e with
  | .bvar i => return arr [text "var", toJson i]
  | .sort u => return arr [text "sort", ← liftM (level u)]
  | .const n us =>
    ensureDeclaration env n
    return arr [text "const", name n, arr (← liftM (us.mapM level))]
  | .app f a => return arr [text "app", ← expr env f, ← expr env a]
  | .forallE _ d b bi => return arr [text "pi", toJson (binderInfo bi), ← expr env d, ← expr env b]
  | .lam _ d b bi => return arr [text "lam", toJson (binderInfo bi), ← expr env d, ← expr env b]
  | .letE _ t v b _ => return arr [text "let", ← expr env t, ← expr env v, ← expr env b]
  | .proj n i v =>
    ensureDeclaration env n
    return arr [text "proj", name n, toJson i, ← expr env v]
  | .lit (.natVal n) =>
    ensureDeclaration env ``Nat
    return arr [text "nat", text (toString n)]
  | .lit (.strVal s) =>
    ensureDeclaration env ``String
    return arr [text "string", text s]
  | .mdata _ inner => return arr [text "mdata", ← expr env inner]
  | .fvar _ => throw "invalid external free variable in closed source"
  | .mvar _ => throw "invalid unresolved expression metavariable"

partial def ensureBlock (env : Environment) (n : Name) : ExportM Unit := do
  let .inductInfo first ← liftM (findInfo env n) | throw "expected inductive header"
  let mut internal : Array Name := #[]
  for family in first.all do
    let .inductInfo info ← liftM (findInfo env family) | throw "missing mutual family"
    internal := internal ++ #[family, mkRecName family] ++ info.ctors.toArray
  -- Reserve the WHOLE mutual group before visiting dependent signatures. The
  -- group itself is appended after all outside dependencies. These are syntax
  -- references, not admitted names or positivity/recursion flags.
  modify fun s => {s with complete := internal.foldl (fun seen n => seen.insert n) s.complete}
  let mut families : Array Json := #[]
  let mut claims : Array Json := #[]
  for family in first.all do
    let .inductInfo info ← liftM (findInfo env family) | throw "missing mutual family"
    let ty ← expr env info.type
    let mut ctors : Array Json := #[]
    for ctor in info.ctors do
      let .ctorInfo c ← liftM (findInfo env ctor) | throw "missing constructor signature"
      ctors := ctors.push (Json.mkObj [("name",name ctor),("type",← expr env c.type)])
    families := families.push (Json.mkObj [("name",name family),("type",ty),
      ("constructors",toJson ctors),("recursor_name",name (mkRecName family))])
    let .recInfo recInfo ← liftM (findInfo env (mkRecName family)) | throw "missing recursor signature"
    claims := claims.push (Json.mkObj [("name",name recInfo.name),
      ("level_params",uparams recInfo.levelParams),("type",← expr env recInfo.type)])
  let block := Json.mkObj [("kind",text "inductive_block"),("level_params",uparams first.levelParams),
    ("parameters",toJson first.numParams),("families",toJson families),("recursor_claims",toJson claims)]
  modify fun s => {s with declarations := s.declarations.push block, visiting := internal.foldl (fun seen n => seen.erase n) s.visiting}

partial def ensureDeclaration (env : Environment) (n : Name) : ExportM Unit := do
  if (← get).complete.contains n then return
  if (← get).visiting.contains n then throw s!"cyclic non-inductive dependency {n}"
  let info ← liftM (findInfo env n)
  modify fun s => {s with visiting := s.visiting.insert n}
  match info with
  | .inductInfo _ => ensureBlock env n
  | .ctorInfo c => ensureBlock env c.induct
  | .recInfo r =>
    let some family := r.all.head? | throw "empty recursor block"
    ensureDeclaration env family
    if !(← get).complete.contains n then
      -- A generated block may also expose auxiliary recursors after nested
      -- restoration. Retain their schemes as claims, never as axioms/bodies.
      let ty ← expr env r.type
      let row := Json.mkObj [("kind",text "recursor_claim"),("name",name n),
        ("level_params",uparams r.levelParams),("type",ty)]
      modify fun s => {s with declarations := s.declarations.push row, complete := s.complete.insert n, visiting := s.visiting.erase n}
  | .quotInfo q =>
    -- init_quot has an implicit dependency on the ordinary Eq block even when
    -- this particular exported quotient signature does not mention Eq. Export
    -- that raw source; no host validation or initialization answer is supplied.
    ensureDeclaration env ``Eq
    let kind := match q.kind with
      | .type => "type" | .ctor => "ctor" | .lift => "lift" | .ind => "ind"
    let ty ← expr env q.type
    let row := Json.mkObj [("kind",text "quot_primitive"),("interface",text kind),
      ("name",name q.name),("level_params",uparams q.levelParams),("type",ty)]
    modify fun s => {s with declarations := s.declarations.push row, complete := s.complete.insert n, visiting := s.visiting.erase n}
  | _ =>
    let (kind, value?) ← match info with
      | .axiomInfo _ =>
        if (getOriginalConstKind? env n).any (· == .axiom) then pure ("axiom",none)
        else throw s!"unavailable body for non-axiom {n}"
      | .defnInfo d => pure ("definition",some d.value)
      | .thmInfo d => pure ("theorem",some d.value)
      | .opaqueInfo d => pure ("opaque",some d.value)
      | _ => throw s!"unsupported declaration kind {n}"
    let ty ← expr env info.type
    let value ← match value? with
      | none => pure Json.null
      | some v => expr env v
    let row := Json.mkObj [("kind",text kind),("name",name n),("level_params",uparams info.levelParams),
      ("type",ty),("value",value)]
    modify fun s => {s with declarations := s.declarations.push row, complete := s.complete.insert n, visiting := s.visiting.erase n}
end

def exportTarget (env : Environment) (n : Name) : Except String Json := do
  let info ← findInfo env n
  let some value := info.value? (allowOpaque := true) | throw "target has no available body"
  let kind := match info with
    | .defnInfo _ => "definition" | .opaqueInfo _ => "opaque" | _ => "theorem"
  let action : ExportM Json := do
    let ty ← expr env info.type
    let body ← expr env value
    return Json.mkObj [("kind",text kind),("name",name n),
      ("level_params",uparams info.levelParams),("type",ty),("value",body)]
  let (target,state) ← action.run {}
  return Json.mkObj [("format",text "leanputer.kernel-source.v1"),("status",text "EXPORTED"),
    ("name",text n.toString),("target",target),("declarations",toJson state.declarations),
    ("provenance",Json.mkObj [("lean_version",text Lean.versionString),
      ("source_name",name n),("preparation",text "original-scheme syntax only; metadata inert; no admission answers")])]

end LeanputerKernelExport

def main (args : List String) : IO UInt32 := do
  let [configPath] := args | throw (IO.userError "usage: lean --run tools/lean/ExportKernel.lean config.json")
  initSearchPath (← findSysroot)
  let config ← IO.ofExcept (Json.parse (← IO.FS.readFile configPath))
  let modules ← IO.ofExcept (config.getObjValAs? (Array String) "modules")
  let targets ← IO.ofExcept (config.getObjValAs? (Array Json) "targets")
  let output ← IO.ofExcept (config.getObjValAs? String "output")
  let env ← importModules (modules.map fun n => {module := n.toName}) {}
  let mut rows : Array String := #[]
  for target in targets do
    let n ← IO.ofExcept (target.getObjValAs? String "name")
    let sourceName ← IO.ofExcept <| match (target.getObjValAs? (Array Json) "name_parts").toOption with
      | some parts => LeanputerKernelExport.decodeName parts
      | none => pure n.toName
    let result := if (target.getObjVal? "levels").isOk then
      .error "scheme export does not accept ground-level requests"
      else LeanputerKernelExport.exportTarget env sourceName
    let row := match result with
      | .ok row => row
      | .error reason => Json.mkObj [("format",toJson "leanputer.kernel-source.v1"),
        ("status",toJson "UNSUPPORTED"),("name",toJson n),("reason",toJson reason),
        ("declarations",Json.null),("target",Json.null)]
    rows := rows.push row.compress
  IO.FS.writeFile output (String.intercalate "\n" rows.toList ++ "\n")
  return 0
