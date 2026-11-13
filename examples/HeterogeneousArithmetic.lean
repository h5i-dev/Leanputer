namespace LeanputerHeterogeneous
noncomputable section
def hAdd010 := HAdd.{0,1,0}
def hMul100 := HMul.{1,0,0}
def hAddRec1012 := @HAdd.rec.{1,0,1,2}
def hMulRec1201 := @HMul.rec.{1,2,0,1}
def distinctCarriers : HAdd Bool Nat PUnit.{1} := ⟨fun _ _ => PUnit.unit.{1}⟩
def eta (A B C : Type) (m : HAdd A B C) : (HAdd.mk m.1 : HAdd A B C) = m := rfl
end
end LeanputerHeterogeneous
