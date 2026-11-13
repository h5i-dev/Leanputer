namespace LeanputerPairs
noncomputable section
def pprod00 := PProd.{0,0}
def pprod01 := PProd.{0,1}
def prod01 := Prod.{0,1}
def pprodRec102 := @PProd.rec.{1,0,2}
def prodRec101 := @Prod.rec.{1,0,1}
def fst (A : Sort 0) (B : Sort 1) (p : PProd A B) : A := p.1
def snd (A : Sort 1) (B : Sort 0) (p : PProd A B) : B := p.2
def eta00 (A B : Sort 0) (p : PProd A B) : (PProd.mk p.1 p.2 : PProd A B) = p := rfl
def eta11 (A B : Sort 1) (p : PProd A B) : (PProd.mk p.1 p.2 : PProd A B) = p := rfl
def prodEta (A B : Type) (p : Prod A B) : (Prod.mk p.1 p.2 : Prod A B) = p := rfl
def neutralRec (A : Sort 0) (B : Sort 1) (p : PProd A B) :
    PProd.rec (motive := fun _ => B) (fun _ b => b) p = p.2 := rfl
end
end LeanputerPairs
