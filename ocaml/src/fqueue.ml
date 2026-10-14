open! Base

(* The classic two-list queue (Okasaki, "Purely Functional Data Structures").

   OCaml lists are singly linked: adding or removing at the head is O(1), but
   the tail is O(n) away. So we keep two lists:

     front : elements in the order they will leave the queue
     back  : elements in REVERSE order of arrival (newest first)

   Enqueue conses onto [back]. Dequeue takes the head of [front]. When [front]
   runs out we reverse [back] once to become the new [front]. Each element is
   reversed at most once, so both operations are O(1) amortised.

   Invariant: if [front] is empty then [back] is empty too. That way the front
   element, when there is one, is always the head of [front], and [peek] never
   has to reverse anything. The smart constructor [make] restores the invariant
   after every change. *)
type 'a t =
  { front : 'a list
  ; back : 'a list
  }

let empty = { front = []; back = [] }
let is_empty t = List.is_empty t.front

let make front back =
  match front with
  | [] -> { front = List.rev back; back = [] }
  | _ :: _ -> { front; back }
;;

let enqueue t x = make t.front (x :: t.back)
let peek t = List.hd t.front

let dequeue t =
  match t.front with
  | [] -> None
  | x :: rest -> Some (x, make rest t.back)
;;

let replace_front t x =
  match t.front with
  | [] -> t
  | _ :: rest -> { t with front = x :: rest }
;;

let to_list t = t.front @ List.rev t.back
let filter t ~f = make (List.filter (to_list t) ~f) []
let fold t ~init ~f = List.fold (to_list t) ~init ~f
