open! Base
open! Stdio
open Lob
open Helpers

let%expect_test "first in, first out, across the internal reversal" =
  let q = List.fold [ 1; 2; 3 ] ~init:Fqueue.empty ~f:Fqueue.enqueue in
  let q =
    match Fqueue.dequeue q with
    | Some (x, q) ->
      printf "out %d\n" x;
      q
    | None -> q
  in
  let q = Fqueue.enqueue q 4 in
  show [%sexp_of: int list] (Fqueue.to_list q);
  [%expect {|
    out 1
    (2 3 4) |}]
;;

let%expect_test "old versions are unaffected (persistence)" =
  let q1 = Fqueue.enqueue Fqueue.empty "a" in
  let q2 = Fqueue.enqueue q1 "b" in
  show [%sexp_of: string list * string list] (Fqueue.to_list q1, Fqueue.to_list q2);
  [%expect {| ((a) (a b)) |}]
;;
