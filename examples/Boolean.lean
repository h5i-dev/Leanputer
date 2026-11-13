namespace LeanputerBool
noncomputable section

def family := Bool
def false := Bool.false
def true := Bool.true
def rec1 := @Bool.rec.{1}

def false_branch (A : Type) (a b : A) (P : A → Prop) (k : P a) :
    P (@Bool.rec.{1} (fun _ => A) a b Bool.false) := k

def true_branch (A : Type) (a b : A) (P : A → Prop) (k : P b) :
    P (@Bool.rec.{1} (fun _ => A) a b Bool.true) := k

end
end LeanputerBool
