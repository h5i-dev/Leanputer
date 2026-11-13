namespace LeanputerOneField
noncomputable section

def inhabFamily0 := Inhabited.{0}
def mulFamily0 := Mul.{0}
def addFamily1 := Add.{1}
def subFamily1 := Subsingleton.{1}
def inhabRec01 := @Inhabited.rec.{0, 1}
def mulRec10 := @Mul.rec.{1, 0}
def subRec10 := @Subsingleton.rec.{1, 0}

def mulField (A : Type) (m : Mul A) : A → A → A := m.1
def addField (A : Type) (m : Add A) : A → A → A := m.1

end
end LeanputerOneField
