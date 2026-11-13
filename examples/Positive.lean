namespace LeanputerPositive
noncomputable section

def true_rec := @True.rec.{1}
def and_rec := @And.rec.{1}
def iff_rec := @Iff.rec.{1}
def nonempty_rec := @Nonempty.rec.{1}
def exists_rec := @Exists.rec.{1}
def or_rec := @Or.rec

def true_k (A : Type) (a : A) (q : True) (P : A → Prop) (h : P a) :
    P (@True.rec.{1} (fun _ => A) a q) := h

def and_eta (p q : Prop) (e : p ∧ q) (P : p → Prop) (h : P e.left) :
    P (@And.rec.{0} p q (fun _ => p) (fun l _ => l) e) := h

def iff_eta (p q : Prop) (e : p ↔ q) (P : (p → q) → Prop) (h : P e.mp) :
    P (@Iff.rec.{0} p q (fun _ => p → q) (fun f _ => f) e) := h

-- Equality of proofs forces recursor type inference and preserves both branches.
theorem nonempty_iota (p : Prop) (h : p) :
    @Nonempty.rec.{0} p (fun _ => p) (fun h => h) ⟨h⟩ = h := rfl

theorem exists_iota (p : Prop) (h : p) :
    @Exists.rec.{0} p (fun _ => p) (fun _ => p) (fun _ h => h) ⟨h,h⟩ = h := rfl

theorem or_left (p q : Prop) (h : p) :
    @Or.rec p q (fun _ => p ∨ q) (fun h => Or.inl h) (fun h => Or.inr h) (Or.inl h) = Or.inl h := rfl

theorem or_right (p q : Prop) (h : q) :
    @Or.rec p q (fun _ => p ∨ q) (fun h => Or.inl h) (fun h => Or.inr h) (Or.inr h) = Or.inr h := rfl

end
end LeanputerPositive
