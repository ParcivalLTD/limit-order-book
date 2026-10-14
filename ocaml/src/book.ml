open! Base

type order_type =
  | Limit of int
  | Market

(* A resting order. Note what is NOT here: no side and no price. Those are
   implied by where the order sits in the book, and a resting order can never be
   a market order. In the Python version every Order carried [price: int | None],
   so "a market order resting in the book" was representable and had to be
   prevented by code. Here it cannot be written down at all. *)
type resting =
  { id : int
  ; agent : string
  ; qty : int
  }

(* One side of the book: a map from price to the FIFO queue of orders at that
   price. [Map.M(Int).t] is Base's balanced binary tree keyed by int, so the
   lowest and highest prices are O(log n) away. That replaces the Python heap
   and its lazy deletion: when a level empties we simply remove the key.

   Invariant: no level in the map is ever an empty queue. *)
type levels = resting Fqueue.t Map.M(Int).t

(* Where a resting order lives, so cancel can find it without searching. *)
type location =
  { side : Side.t
  ; price : int
  ; owner : string
  }

type t =
  { bids : levels
  ; asks : levels
  ; index : location Map.M(Int).t (* order id -> location *)
  ; next_id : int
  ; time : int
  }

let empty =
  { bids = Map.empty (module Int)
  ; asks = Map.empty (module Int)
  ; index = Map.empty (module Int)
  ; next_id = 1
  ; time = 0
  }
;;

let time t = t.time

(* ------------------------------------------------------------------ helpers *)

let levels t (side : Side.t) =
  match side with
  | Buy -> t.bids
  | Sell -> t.asks
;;

let with_levels t (side : Side.t) levels =
  match side with
  | Buy -> { t with bids = levels }
  | Sell -> { t with asks = levels }
;;

(* Write a queue back into a side, removing the level if the queue is empty.
   This one function is what keeps the "no empty levels" invariant. *)
let set_level levels ~price queue =
  if Fqueue.is_empty queue
  then Map.remove levels price
  else Map.set levels ~key:price ~data:queue
;;

(* The best price on a side: highest bid, lowest ask. *)
let best_price levels (side : Side.t) =
  let best =
    match side with
    | Buy -> Map.max_elt levels
    | Sell -> Map.min_elt levels
  in
  Option.map best ~f:fst
;;

(* -------------------------------------------------------------------- reads *)

let best_bid t = best_price t.bids Buy
let best_ask t = best_price t.asks Sell

let spread t =
  match best_bid t, best_ask t with
  | Some bid, Some ask -> Some (ask - bid)
  | _ -> None
;;

let mid t =
  match best_bid t, best_ask t with
  | Some bid, Some ask -> Some (Float.of_int (bid + ask) /. 2.)
  | _ -> None
;;

let depth_at t side price =
  match Map.find (levels t side) price with
  | None -> 0
  | Some queue -> Fqueue.fold queue ~init:0 ~f:(fun total o -> total + o.qty)
;;

let snapshot t (side : Side.t) =
  let ascending = Map.keys (levels t side) in
  let best_first =
    match side with
    | Buy -> List.rev ascending
    | Sell -> ascending
  in
  List.map best_first ~f:(fun price -> price, depth_at t side price)
;;

let open_order_ids t ~agent =
  Map.filter t.index ~f:(fun loc -> String.equal loc.owner agent) |> Map.keys
;;

(* ----------------------------------------------------------------- matching *)

(* Does an incoming order on [side] trade against a resting price? *)
let crosses (side : Side.t) order_type ~resting_price =
  match order_type, side with
  | Market, _ -> true
  | Limit limit, Buy -> limit >= resting_price
  | Limit limit, Sell -> limit <= resting_price
;;

(* The matching loop. Takes the book and the quantity still to fill, consumes
   the opposite side best price first and oldest order first, and returns the
   new book, the unfilled remainder, and the trades in execution order.

   It is written as a recursive function instead of a while loop. Each call does
   exactly one fill against the order at the front of the best level, then calls
   itself with the smaller remainder. [trades] accumulates in reverse (consing
   onto a list is O(1)) and is reversed once at the end. Because the recursive
   call is the last thing the function does, OCaml compiles it to a loop: no
   stack growth. *)
let rec fill t ~agent ~side ~order_type ~remaining ~trades =
  let opposite = Side.opposite side in
  let book_side = levels t opposite in
  match best_price book_side opposite with
  | Some price when remaining > 0 && crosses side order_type ~resting_price:price ->
    let queue = Map.find_exn book_side price in
    let maker = Option.value_exn (Fqueue.peek queue) in
    let filled = Int.min maker.qty remaining in
    let trade =
      { Trade.price (* the maker's price, always *)
      ; quantity = filled
      ; maker = maker.agent
      ; taker = agent
      ; taker_side = side
      ; time = t.time
      }
    in
    let t =
      if filled = maker.qty
      then (
        (* The maker is completely filled: it leaves the queue and the index. *)
        let _, rest = Option.value_exn (Fqueue.dequeue queue) in
        let t = with_levels t opposite (set_level book_side ~price rest) in
        { t with index = Map.remove t.index maker.id })
      else (
        (* Partial fill: the maker keeps its place with a smaller quantity. *)
        let queue = Fqueue.replace_front queue { maker with qty = maker.qty - filled } in
        with_levels t opposite (set_level book_side ~price queue))
    in
    fill t ~agent ~side ~order_type ~remaining:(remaining - filled) ~trades:(trade :: trades)
  | _ -> t, remaining, List.rev trades
;;

let rest t ~id ~agent ~side ~price ~qty =
  let book_side = levels t side in
  let queue = Option.value (Map.find book_side price) ~default:Fqueue.empty in
  let queue = Fqueue.enqueue queue { id; agent; qty } in
  let t = with_levels t side (Map.set book_side ~key:price ~data:queue) in
  { t with index = Map.set t.index ~key:id ~data:{ side; price; owner = agent } }
;;

let validate ~quantity order_type =
  match order_type with
  | _ when quantity <= 0 -> Or_error.errorf "quantity must be positive, got %d" quantity
  | Limit price when price <= 0 -> Or_error.errorf "price must be positive, got %d" price
  | Limit _ | Market -> Ok ()
;;

let submit t ~agent ~side ~quantity order_type =
  (* [Result.map] runs the function only if validation returned [Ok]; an
     [Error] passes straight through, and the book is untouched. *)
  Result.map (validate ~quantity order_type) ~f:(fun () ->
    let id = t.next_id in
    let t = { t with next_id = id + 1; time = t.time + 1 } in
    let t, remaining, trades =
      fill t ~agent ~side ~order_type ~remaining:quantity ~trades:[]
    in
    match order_type with
    | Limit price when remaining > 0 ->
      rest t ~id ~agent ~side ~price ~qty:remaining, Some id, trades
    | Limit _ | Market -> t, None, trades)
;;

let cancel t id =
  match Map.find t.index id with
  | None -> None
  | Some { side; price; owner = _ } ->
    let book_side = levels t side in
    let queue = Fqueue.filter (Map.find_exn book_side price) ~f:(fun o -> o.id <> id) in
    let t = with_levels t side (set_level book_side ~price queue) in
    Some { t with index = Map.remove t.index id }
;;

let cancel_all t ~agent =
  List.fold (open_order_ids t ~agent) ~init:(t, 0) ~f:(fun (t, cancelled) id ->
    match cancel t id with
    | Some t -> t, cancelled + 1
    | None -> t, cancelled)
;;
