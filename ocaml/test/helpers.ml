open! Base
open! Stdio
open Lob

(* Submit an order and fail the test loudly if it is rejected. *)
let submit book ~agent side quantity order_type =
  Or_error.ok_exn (Book.submit book ~agent ~side ~quantity order_type)
;;

(* Submit and keep only the new book, for setting a scenario up. *)
let place book ~agent side quantity order_type =
  let book, _, _ = submit book ~agent side quantity order_type in
  book
;;

(* [show sexp_of value] prints any value we have an s-expression converter for.
   [%sexp_of: int option] is generated code: a function int option -> Sexp.t. *)
let show sexp_of value = print_s (sexp_of value)

let print_trades trades = List.iter trades ~f:(fun t -> print_s (Trade.sexp_of_t t))

let print_book book =
  show
    [%sexp_of: (string * (int * int) list) list]
      [ "bids", Book.snapshot book Buy; "asks", Book.snapshot book Sell ]
;;
