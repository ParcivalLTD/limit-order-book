(** A persistent (immutable) first-in-first-out queue.

    "Persistent" means every operation returns a new queue and leaves the old one
    untouched, so a book that holds a queue can be kept around and compared with
    the book after a trade. That is what makes the property tests cheap. *)

type 'a t

val empty : 'a t
val is_empty : 'a t -> bool

(** Add to the back. Amortised O(1). *)
val enqueue : 'a t -> 'a -> 'a t

(** The front element, if any. O(1). *)
val peek : 'a t -> 'a option

(** Remove the front element. Amortised O(1). *)
val dequeue : 'a t -> ('a * 'a t) option

(** Replace the front element (used for a partial fill, which must keep the
    resting order's place in the queue). O(1). No-op on an empty queue. *)
val replace_front : 'a t -> 'a -> 'a t

(** Keep only the elements satisfying [f], preserving order. O(n). *)
val filter : 'a t -> f:('a -> bool) -> 'a t

val fold : 'a t -> init:'acc -> f:('acc -> 'a -> 'acc) -> 'acc
val to_list : 'a t -> 'a list
