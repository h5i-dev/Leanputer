-- Source-only corpus; proof expressions and dependencies are exported after
-- Lean elaboration. There are no Python copies of their proofs/types.
import Lean

namespace LeanputerCorpus
universe u v w

def poly_id (A : Sort u) (x : A) : A := x
theorem imp_id (P : Prop) : P → P := fun p => p
def constant (A : Sort u) (B : Sort v) (a : A) (_ : B) : A := a
def compose (A : Sort u) (B : Sort v) (C : Sort w)
    (f : A → B) (g : B → C) (a : A) : C := g (f a)
def dependent_id (A : Sort u) (B : A → Sort v) (a : A) (b : B a) : B a := b
def dependent_apply (A : Sort u) (B : A → Sort v)
    (f : (a : A) → B a) (a : A) : B a := f a
def dependent_compose (A : Sort u) (B : A → Sort v)
    (C : (a : A) → B a → Sort w) (f : (a : A) → B a)
    (g : (a : A) → (b : B a) → C a b) (a : A) : C a (f a) := g a (f a)
theorem beta_type (P : Prop) : (fun Q : Prop => Q) P → P := fun p => p

def PropAlias : Type := Prop
theorem delta_type (P : PropAlias) : P → P := fun p => p

def use_library_id (A : Sort u) (a : A) : A := id a
def use_library_comp (A B C : Type) (f : A → B) (g : B → C) (a : A) : C :=
  (g ∘ f) a

theorem forall_id (A : Sort u) (P : A → Prop) (h : ∀ a, P a) : ∀ a, P a := fun a => h a
theorem forall_imp (A : Sort u) (P Q : A → Prop) (h : ∀ a, P a → Q a)
    (p : ∀ a, P a) : ∀ a, Q a := fun a => h a (p a)
theorem dependent_proof (A : Sort u) (B : A → Sort v)
    (P : (a : A) → B a → Prop) (f : (a : A) → B a)
    (h : (a : A) → (b : B a) → P a b) (a : A) : P a (f a) := h a (f a)

theorem eta_type (A B : Type) (F : (A → B) → Prop) (f : A → B)
    (h : F f) : F (fun a => f a) := h
theorem proof_irrelevance_type (P : Prop) (p q : P) (F : P → Prop)
    (h : F p) : F q := h
theorem use_opaque_proof (P : Prop) (p : P) : P := imp_id P p

-- An explicitly unsupported inductive/recursor dependency.
theorem unsupported_nat (n : Nat) : n = n := rfl
end LeanputerCorpus
