namespace LeanputerDecidable
noncomputable section

def family := @Decidable
def yes := @Decidable.isTrue
def no := @Decidable.isFalse
def rec1 := @Decidable.rec.{1}

def true_branch (A : Type) (a b : A) (p : Prop) (h : p) (P : A → Prop) (k : P a) :
    P (@Decidable.rec.{1} p (fun _ => A) (fun _ => b) (fun _ => a) (Decidable.isTrue h)) := k

def false_branch (A : Type) (a b : A) (p : Prop) (h : p → False) (P : A → Prop) (k : P b) :
    P (@Decidable.rec.{1} p (fun _ => A) (fun _ => b) (fun _ => a) (Decidable.isFalse h)) := k

end
end LeanputerDecidable
