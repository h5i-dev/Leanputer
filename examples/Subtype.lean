namespace LeanputerSubtype
noncomputable section

def family0 := @Subtype.{0}
def family1 := @Subtype.{1}
def mk1 := @Subtype.mk.{1}
def rec10 := @Subtype.rec.{1,0}

def val (A : Type) (p : A → Prop) (s : Subtype p) : A := s.val
def property (A : Type) (p : A → Prop) (s : Subtype p) : p s.val := s.property

def eta (A : Type) (p : A → Prop) (s : Subtype p) (P : Subtype p → Prop) (h : P s) :
    P (@Subtype.mk.{1} A p s.val s.property) := h

def rec_val (A : Type) (p : A → Prop) (s : Subtype p) (P : A → Prop) (h : P s.val) :
    P (@Subtype.rec.{1,1} A p (fun _ => A) (fun val _ => val) s) := h

def rec_eta (A : Type) (p : A → Prop) (s : Subtype p) (P : Subtype p → Prop) (h : P s) :
    P (@Subtype.rec.{1,1} A p (fun _ => Subtype p) (fun val property => ⟨val,property⟩) s) := h

end
end LeanputerSubtype
