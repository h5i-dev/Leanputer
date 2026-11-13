import Lean

/- Source-level contracts for the generic algorithms, not input certificates.
   The Python spec tests instantiate these telescope/recursor operations with
   opaque numeric symbol identities. Lean is used only for offline validation. -/
set_option autoImplicit false
universe u

namespace KernelAlgorithms
noncomputable section

inductive DependentFields (A : Type) (B : A → Type) : Type where
  | mk (x : A) (v : B x) (y : A) (w : B y) : DependentFields A B

mutual
  inductive Left (A : Type) : A → Type where
    | seed (x : A) : Left A x
    | step (x : A) (next : (y : A) → Right A y) : Left A x
  inductive Right (A : Type) : A → Type where
    | join (x : A) (prev : Left A x) : Right A x
end

-- Fields precede all IHs; a functional recursive field passes its own index
-- to the other family's motive and recursor.
example (A : Type)
    (mLeft : (x : A) → Left A x → Sort u)
    (mRight : (x : A) → Right A x → Sort u)
    (seed : (x : A) → mLeft x (Left.seed x))
    (step : (x : A) → (next : (y : A) → Right A y) →
      ((y : A) → mRight y (next y)) → mLeft x (Left.step x next))
    (join : (x : A) → (prev : Left A x) → mLeft x prev → mRight x (Right.join x prev))
    (x : A) (major : Left A x) : mLeft x major :=
  @Left.rec A mLeft mRight seed step join x major

example (A : Type)
    (mLeft : (x : A) → Left A x → Sort u)
    (mRight : (x : A) → Right A x → Sort u)
    (seed : (x : A) → mLeft x (Left.seed x))
    (step : (x : A) → (next : (y : A) → Right A y) →
      ((y : A) → mRight y (next y)) → mLeft x (Left.step x next))
    (join : (x : A) → (prev : Left A x) → mLeft x prev → mRight x (Right.join x prev))
    (x : A) (next : (y : A) → Right A y) :
    @Left.rec A mLeft mRight seed step join x (Left.step x next) =
      step x next (fun y => @Right.rec A mLeft mRight seed step join y (next y)) := rfl

-- Lean's command elaborator forbids a possibly-Prop result universe. The
-- pinned raw KERNEL accepts it with Prop-only elimination. Test that authority
-- directly rather than silently treating elaborator restrictions as kernel
-- semantics, or grounding the declaration before it reaches the checker.
#eval do
  let env ← Lean.mkEmptyEnvironment
  let family := Lean.mkConst `KernelAlgorithms.RawMaybeProp [.param `u]
  let decl := Lean.Declaration.inductDecl [`u] 0
    [{ name := `KernelAlgorithms.RawMaybeProp
       type := .sort (.param `u)
       ctors := [{ name := `KernelAlgorithms.RawMaybeProp.first, type := family },
                 { name := `KernelAlgorithms.RawMaybeProp.second, type := family }] }] false
  match Lean.Kernel.Environment.addDecl env.toKernelEnv {} decl with
  | .ok _ => IO.println "Raw symbolic-universe kernel admission passed"
  | .error _ => throw <| IO.userError "Raw symbolic-universe kernel admission failed"

end
end KernelAlgorithms
