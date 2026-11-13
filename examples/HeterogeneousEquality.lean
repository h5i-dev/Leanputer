namespace LeanputerHEq
noncomputable section

def family := @HEq.{1}
def refl := @HEq.refl.{1}
def rec01 := @HEq.rec.{0,1}

def k (A : Type) (a : A) (q : HEq a a) (P : A → Prop) (h : P a) :
    P (@HEq.rec.{1,1} A a (fun {_B : Type} (_b : _B) (_h : HEq a _b) => A) a A a q) := h

def iota (A : Type) (a : A) (P : A → Prop) (h : P a) :
    P (@HEq.rec.{1,1} A a (fun {_B : Type} (_b : _B) (_h : HEq a _b) => A) a A a (HEq.refl a)) := h

end
end LeanputerHEq
