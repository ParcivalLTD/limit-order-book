(* Property-based tests: instead of hand-picked scenarios, QCheck generates
   thousands of random order streams and checks rules that must hold for all
   of them. If one fails, QCheck shrinks it to a minimal counterexample. *)

open! Base
open! Stdio
open Lob

type op =
  | Submit of Side.t * int * Book.order_type
  | Cancel of int

let gen_side = QCheck.Gen.map (fun b -> if b then Side.Buy else Side.Sell) QCheck.Gen.bool

(* A weighted choice: 6 in 9 limit orders, 1 in 9 market orders, 2 in 9 cancels.
   Built from [int_range] and [>>=] (bind) so it compiles on every QCheck
   version; [Gen.frequency] is deprecated from qcheck-core 0.91 on. *)
let gen_op =
  let open QCheck.Gen in
  int_range 0 8
  >>= fun k ->
  if k < 6
  then
    map3
      (fun side qty price -> Submit (side, qty, Book.Limit price))
      gen_side
      (int_range 1 20)
      (int_range 95 105)
  else if k < 7
  then map2 (fun side qty -> Submit (side, qty, Book.Market)) gen_side (int_range 1 30)
  else map (fun id -> Cancel id) (int_range 1 60)
;;

let gen_ops = QCheck.Gen.(list_size (int_range 1 80) gen_op)
let resting book side = List.sum (module Int) (Book.snapshot book side) ~f:snd

(* Checks one step and returns the new book. Raises on any violation. *)
let step book op =
  match op with
  | Cancel id -> Option.value (Book.cancel book id) ~default:book
  | Submit (side, quantity, order_type) ->
    let book', id, trades =
      Or_error.ok_exn (Book.submit book ~agent:"x" ~side ~quantity order_type)
    in
    let filled = List.sum (module Int) trades ~f:(fun t -> t.quantity) in
    let rested = resting book' side - resting book side in
    (* 1. Every contract filled came out of the opposite side of the book. *)
    assert (resting book (Side.opposite side) - resting book' (Side.opposite side) = filled);
    (* 2. A limit order is fully accounted for: filled plus rested. A market
          order never rests and never over-fills. *)
    (match order_type with
     | Limit _ -> assert (filled + rested = quantity && Bool.equal (rested > 0) (Option.is_some id))
     | Market -> assert (rested = 0 && filled <= quantity && Option.is_none id));
    (* 3. The book is never left crossed. *)
    (match Book.best_bid book', Book.best_ask book' with
     | Some bid, Some ask -> assert (bid < ask)
     | _ -> ());
    (* 4. Trades walk prices monotonically away from the touch (best first). *)
    let prices = List.map trades ~f:(fun t -> t.price) in
    let sorted =
      List.is_sorted prices ~compare:(match side with
        | Buy -> Int.compare
        | Sell -> Fn.flip Int.compare)
    in
    assert sorted;
    book'
;;

let invariants =
  QCheck.Test.make
    ~count:5000
    ~name:"conserved, never crossed, best price first"
    (QCheck.make gen_ops)
    (fun ops ->
      let (_ : Book.t) = List.fold ops ~init:Book.empty ~f:step in
      true)
;;

let%expect_test "properties hold on 5,000 random order streams" =
  QCheck.Test.check_exn ~rand:(Stdlib.Random.State.make [| 42 |]) invariants;
  print_endline "ok";
  [%expect {| ok |}]
;;