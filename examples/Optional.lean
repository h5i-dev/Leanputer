namespace LeanputerOption
noncomputable section

def family0 := Option.{0}
def family1 := Option.{1}
def none0 := @Option.none.{0}
def some0 := @Option.some.{0}
def rec01 := @Option.rec.{0, 1}
def rec10 := @Option.rec.{1, 0}

def none_branch (A : Type) (a b : A) (P : A → Prop) (k : P a) :
    P (@Option.rec.{1, 0} A (fun _ => A) a (fun _ => b) Option.none) := k

def some_branch (A : Type) (a b : A) (P : A → Prop) (k : P b) :
    P (@Option.rec.{1, 0} A (fun _ => A) a (fun x => x) (Option.some b)) := k

end
end LeanputerOption
