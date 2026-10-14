open! Base

(* One fill. [maker] was resting in the book, [taker] crossed the spread to hit it.

   The trade always prints at the maker's price, so an aggressive taker gets any
   price improvement. That is what a real book does, and it is what makes being
   early in the queue worth something. *)
type t =
  { price : int
  ; quantity : int
  ; maker : string
  ; taker : string
  ; taker_side : Side.t
  ; time : int
  }
[@@deriving sexp, compare, equal]

(* Change in [agent]'s inventory from this trade: the taker moves in the
   direction it traded, the maker the opposite way, anyone else not at all. *)
let signed_quantity_for t ~agent =
  if String.equal agent t.taker
  then Side.sign t.taker_side * t.quantity
  else if String.equal agent t.maker
  then Side.sign (Side.opposite t.taker_side) * t.quantity
  else 0
;;
