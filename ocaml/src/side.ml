open! Base

(* Which side of the market an order is on.

   In the Python version this was an Enum whose values were 1 and -1, and the
   sign was read off the value. Here the two cases are plain constructors and the
   sign is a separate function, so nothing can depend on an accidental numeric
   encoding. Every [match] on a side is checked by the compiler for
   exhaustiveness: forget a case and the build fails. *)
type t =
  | Buy
  | Sell
[@@deriving sexp, compare, equal]

let opposite = function
  | Buy -> Sell
  | Sell -> Buy
;;

(* +1 for a buy, -1 for a sell. Used to sign inventory changes. *)
let sign = function
  | Buy -> 1
  | Sell -> -1
;;
