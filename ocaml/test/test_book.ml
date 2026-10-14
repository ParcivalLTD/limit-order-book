(* The 15 tests from tests/test_book.py, one for one, as expect tests.

   An expect test prints things, and the expected output is written in the
   source inside [%expect {| ... |}]. [dune test] runs the code and diffs what
   was printed against what is written. *)

open! Base
open! Stdio
open Lob
open Helpers

let%expect_test "resting orders do not trade" =
  let book = place Book.empty ~agent:"a" Buy 10 (Limit 99) in
  let book, _, trades = submit book ~agent:"b" Sell 10 (Limit 101) in
  print_trades trades;
  show
    [%sexp_of: int option * int option * int option * float option]
      (Book.best_bid book, Book.best_ask book, Book.spread book, Book.mid book);
  [%expect {| ((99) (101) (2) (100)) |}]
;;

let%expect_test "price priority: best level fills first" =
  let book = place Book.empty ~agent:"far" Buy 10 (Limit 98) in
  let book = place book ~agent:"near" Buy 10 (Limit 99) in
  let _, _, trades = submit book ~agent:"taker" Sell 10 (Limit 98) in
  print_trades trades;
  [%expect {|
    ((price 99) (quantity 10) (maker near) (taker taker) (taker_side Sell)
     (time 3)) |}]
;;

let%expect_test "time priority within a level is FIFO" =
  let book = place Book.empty ~agent:"first" Buy 5 (Limit 100) in
  let book = place book ~agent:"second" Buy 5 (Limit 100) in
  let book, _, trades = submit book ~agent:"taker" Sell 7 (Limit 100) in
  print_trades trades;
  printf "depth left at 100: %d\n" (Book.depth_at book Buy 100);
  [%expect {|
    ((price 100) (quantity 5) (maker first) (taker taker) (taker_side Sell)
     (time 3))
    ((price 100) (quantity 2) (maker second) (taker taker) (taker_side Sell)
     (time 3))
    depth left at 100: 3 |}]
;;

let%expect_test "trade prints at the maker's price" =
  let book = place Book.empty ~agent:"maker" Sell 10 (Limit 100) in
  (* An aggressive buy priced through the offer still pays the resting price. *)
  let _, _, trades = submit book ~agent:"taker" Buy 10 (Limit 105) in
  print_trades trades;
  [%expect {|
    ((price 100) (quantity 10) (maker maker) (taker taker) (taker_side Buy)
     (time 2)) |}]
;;

let%expect_test "partial fill rests the remainder" =
  let book = place Book.empty ~agent:"maker" Sell 4 (Limit 100) in
  let book, id, trades = submit book ~agent:"taker" Buy 10 (Limit 100) in
  print_trades trades;
  show [%sexp_of: int option] id;
  print_book book;
  [%expect {|
    ((price 100) (quantity 4) (maker maker) (taker taker) (taker_side Buy)
     (time 2))
    (2)
    ((bids ((100 6))) (asks ())) |}]
;;

let%expect_test "market order walks levels, then discards the remainder" =
  let book = place Book.empty ~agent:"m1" Sell 3 (Limit 100) in
  let book = place book ~agent:"m2" Sell 3 (Limit 101) in
  let book, id, trades = submit book ~agent:"taker" Buy 10 Market in
  print_trades trades;
  show [%sexp_of: int option] id;
  print_book book;
  [%expect {|
    ((price 100) (quantity 3) (maker m1) (taker taker) (taker_side Buy) (time 3))
    ((price 101) (quantity 3) (maker m2) (taker taker) (taker_side Buy) (time 3))
    ()
    ((bids ()) (asks ())) |}]
;;

let%expect_test "market order into an empty book does nothing" =
  let book, id, trades = submit Book.empty ~agent:"taker" Buy 10 Market in
  show [%sexp_of: int option * int] (id, List.length trades);
  print_book book;
  [%expect {|
    (() 0)
    ((bids ()) (asks ())) |}]
;;

let%expect_test "cancel removes liquidity and is idempotent" =
  let book, id, _ = submit Book.empty ~agent:"a" Buy 10 (Limit 100) in
  let id = Option.value_exn id in
  let book = Option.value_exn (Book.cancel book id) in
  show [%sexp_of: int option] (Book.best_bid book);
  show [%sexp_of: bool] (Option.is_some (Book.cancel book id));
  [%expect {|
    ()
    false |}]
;;

let%expect_test "cancel_all only touches the named agent" =
  let book = place Book.empty ~agent:"mm" Buy 5 (Limit 99) in
  let book = place book ~agent:"mm" Sell 5 (Limit 101) in
  let book = place book ~agent:"other" Buy 5 (Limit 98) in
  let book, cancelled = Book.cancel_all book ~agent:"mm" in
  printf "cancelled %d\n" cancelled;
  print_book book;
  [%expect {|
    cancelled 2
    ((bids ((98 5))) (asks ())) |}]
;;

let%expect_test "book is never left crossed" =
  let book = place Book.empty ~agent:"a" Sell 5 (Limit 100) in
  let book = place book ~agent:"b" Buy 5 (Limit 100) in
  show [%sexp_of: int option * int option] (Book.best_bid book, Book.best_ask book);
  [%expect {| (() ()) |}]
;;

let%expect_test "an emptied level does not come back" =
  (* In Python this exercised the heap's lazy deletion. The OCaml book removes a
     level the moment it empties, so this checks that invariant instead. *)
  let book = place Book.empty ~agent:"a" Buy 5 (Limit 100) in
  let book = place book ~agent:"t" Sell 5 (Limit 100) in
  show [%sexp_of: int option] (Book.best_bid book);
  let book = place book ~agent:"b" Buy 5 (Limit 99) in
  show [%sexp_of: int option] (Book.best_bid book);
  [%expect {|
    ()
    (99) |}]
;;

let%expect_test "quantity is conserved across a multi-level sweep" =
  let book =
    List.fold [ 100; 101; 102 ] ~init:Book.empty ~f:(fun book price ->
      place book ~agent:"mm" Sell 4 (Limit price))
  in
  let book, _, trades = submit book ~agent:"taker" Buy 9 Market in
  let filled = List.sum (module Int) trades ~f:(fun t -> t.quantity) in
  let remaining = List.sum (module Int) (Book.snapshot book Sell) ~f:snd in
  printf "filled %d + remaining %d = %d\n" filled remaining (filled + remaining);
  [%expect {| filled 9 + remaining 3 = 12 |}]
;;

let%expect_test "signed quantity is equal and opposite" =
  let book = place Book.empty ~agent:"maker" Sell 5 (Limit 100) in
  let _, _, trades = submit book ~agent:"taker" Buy 5 Market in
  let trade = List.hd_exn trades in
  List.iter [ "taker"; "maker"; "bystander" ] ~f:(fun agent ->
    printf "%-10s %d\n" agent (Trade.signed_quantity_for trade ~agent));
  [%expect {|
    taker      5
    maker      -5
    bystander  0 |}]
;;

let%expect_test "rejects nonsense orders" =
  let show result =
    match result with
    | Ok _ -> print_endline "accepted"
    | Error err -> print_s (Error.sexp_of_t err)
  in
  show (Book.submit Book.empty ~agent:"a" ~side:Buy ~quantity:0 (Limit 100));
  show (Book.submit Book.empty ~agent:"a" ~side:Buy ~quantity:5 (Limit (-1)));
  [%expect {|
    "quantity must be positive, got 0"
    "price must be positive, got -1" |}]
;;

let%expect_test "snapshot is ordered best first" =
  let book =
    List.fold [ 98; 100; 99 ] ~init:Book.empty ~f:(fun book price ->
      place book ~agent:"a" Buy 1 (Limit price))
  in
  let book =
    List.fold [ 103; 101; 102 ] ~init:book ~f:(fun book price ->
      place book ~agent:"a" Sell 1 (Limit price))
  in
  print_book book;
  [%expect {| ((bids ((100 1) (99 1) (98 1))) (asks ((101 1) (102 1) (103 1)))) |}]
;;
