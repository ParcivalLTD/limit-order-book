(** A single-instrument limit order book with price-time priority.

    The book is immutable: every operation returns a new book and leaves the old
    one valid. Prices and quantities are integers (ticks and contracts). *)

open! Base

(** A limit order has a price; a market order takes whatever is there. *)
type order_type =
  | Limit of int
  | Market

(** The book. Its fields are hidden, so code outside this file can only change a
    book through the functions below, which keep its invariants. *)
type t

val empty : t

(** {2 Reading the book} *)

val best_bid : t -> int option
val best_ask : t -> int option
val spread : t -> int option
val mid : t -> float option

(** Total resting quantity at one price on one side (0 if none). *)
val depth_at : t -> Side.t -> int -> int

(** (price, resting quantity) for every level, best price first. *)
val snapshot : t -> Side.t -> (int * int) list

(** Ids of [agent]'s resting orders, ascending. *)
val open_order_ids : t -> agent:string -> int list

(** Number of submissions so far; trades are stamped with it. *)
val time : t -> int

(** {2 Changing the book} *)

(** Submit an order. On success returns the new book, the id of the order if any
    of it is now resting, and the trades it caused (in execution order).

    A limit order that is not completely filled rests at its price. A market
    order never rests: whatever it cannot fill is dropped. A non-positive
    quantity or price is an error, and the book is left unchanged. *)
val submit
  :  t
  -> agent:string
  -> side:Side.t
  -> quantity:int
  -> order_type
  -> (t * int option * Trade.t list) Or_error.t

(** Remove a resting order. [None] if it is not in the book (already filled,
    already cancelled, or never existed). *)
val cancel : t -> int -> t option

(** Cancel every resting order of [agent]; returns how many were removed. *)
val cancel_all : t -> agent:string -> t * int
