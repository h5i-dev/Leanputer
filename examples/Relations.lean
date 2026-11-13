namespace LeanputerRelations
noncomputable section

def ltFamily0 := LT.{0}
def leFamily1 := LE.{1}
def ltRec10 := @LT.rec.{1, 0}
def leRec01 := @LE.rec.{0, 1}
def ltField (A : Type) (r : LT A) : A → A → Prop := r.1
def leEta (A : Type) (r : LE A) : (LE.mk r.1 : LE A) = r := rfl

def ltIota (A : Type) (r : A → A → Prop) :
    LT.rec (motive := fun _ => A → A → Prop) (fun x => x) (LT.mk r) = r := rfl
end
end LeanputerRelations
