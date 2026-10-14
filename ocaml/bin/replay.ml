(* Replays a stream of operations against the OCaml book and prints, for each
   one, what happened and the resulting book. diff/differential.py runs the same
   stream through the Python engine and requires the two outputs to be identical.

   Input, one operation per line:
     S <agent> <B|S> <quantity> <price|M>    submit (M = market order)
     C <order id>                            cancel
     X <agent>                               cancel all of an agent's orders *)

open! Base
open! Stdio
open Lob

let side_of_string = function
  | "B" -> Side.Buy
  | "S" -> Side.Sell
  | s -> failwith ("bad side " ^ s)
;;

let side_to_string : Side.t -> string = function
  | Buy -> "B"
  | Sell -> "S"
;;

let levels_to_string levels =
  List.map levels ~f:(fun (price, qty) -> Printf.sprintf "%d@%d" price qty)
  |> String.concat ~sep:","
;;

let book_to_string book =
  Printf.sprintf
    "B:%s A:%s"
    (levels_to_string (Book.snapshot book Buy))
    (levels_to_string (Book.snapshot book Sell))
;;

let trade_to_string (t : Trade.t) =
  Printf.sprintf
    "%d,%d,%s,%s,%s,%d"
    t.price
    t.quantity
    t.maker
    t.taker
    (side_to_string t.taker_side)
    t.time
;;

let apply book line =
  match String.split line ~on:' ' with
  | [ "S"; agent; side; qty; price ] ->
    let order_type =
      if String.equal price "M" then Book.Market else Limit (Int.of_string price)
    in
    (match
       Book.submit book ~agent ~side:(side_of_string side) ~quantity:(Int.of_string qty) order_type
     with
     | Error _ -> book, "E"
     | Ok (book, id, trades) ->
       let id = Option.value_map id ~default:"-" ~f:Int.to_string in
       let trades = List.map trades ~f:trade_to_string |> String.concat ~sep:";" in
       book, Printf.sprintf "S %s [%s]" id trades)
  | [ "C"; id ] ->
    (match Book.cancel book (Int.of_string id) with
     | Some book -> book, "C true"
     | None -> book, "C false")
  | [ "X"; agent ] ->
    let book, n = Book.cancel_all book ~agent in
    book, Printf.sprintf "X %d" n
  | _ -> failwith ("bad line: " ^ line)
;;

let () =
  let (_ : Book.t) =
    In_channel.fold_lines In_channel.stdin ~init:Book.empty ~f:(fun book line ->
      let book, result = apply book line in
      printf "%s | %s\n" result (book_to_string book);
      book)
  in
  ()
;;
