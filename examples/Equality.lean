namespace LeanputerEquality

def family := @Eq.{1}
def refl := @Eq.refl.{1}
def rec01 := @Eq.rec.{0,1}

theorem symmetry {A : Type} {a b : A} (h : a=b) : b=a := h.symm

def cast_rfl (A : Type) (a : A) : A := Eq.mp (Eq.refl A) a

def cast_iota_type (A : Type) (a : A) (P : A → Prop) (h : P a) :
    P (Eq.mp (Eq.refl A) a) := h

def cast_k_type (A : Type) (a : A) (P : A → Prop) (h : P a) :
    P (Eq.mp (Eq.symm (Eq.refl A)) a) := h

end LeanputerEquality

namespace LeanputerEquality

def direct_cast_type (A : Type) (a : A) (P : A → Prop) (h : P a) :
    P (@Eq.rec.{1,1} A a (fun (_b : A) (_e : a = _b) => A) a a (Eq.refl a)) := h

def direct_k_type (A : Type) (a : A) (q : a = a) (P : A → Prop) (h : P a) :
    P (@Eq.rec.{1,1} A a (fun (_b : A) (_e : a = _b) => A) a a q) := h

end LeanputerEquality
