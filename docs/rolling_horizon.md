# Rolling-Horizon Allocation

## 1. Static versus rolling-horizon information

The static DCA model receives every realised demand simultaneously.

A rolling-horizon model instead receives one booking request at each decision
event.

At event \(e\), demands are partitioned into:

- prior demands already processed;
- the current arriving demand;
- future demands not yet revealed.

## 2. Booking-event sequence

Requests are sorted using:

\[
(t_k^{res},k).
\]

The first component is the reservation time.

The demand identifier provides deterministic ordering when several requests
share the same reservation time.

## 3. Information boundary

For event \(e\):

\[
K_e^{prior}
=
\{k: sequence(k)<e\},
\]

\[
K_e^{known}
=
K_e^{prior}\cup\{k_e\},
\]

and:

\[
K_e^{future}
=
\{k: sequence(k)>e\}.
\]

The baseline DCA decision at event \(e\) must not use realised attributes of
\(K_e^{future}\).

Revenue management may later use probability distributions for future demand,
but not its realised future values.

## 4. Equal-time requests

Requests with the same reservation time are still processed sequentially.

No physical network time passes between those booking decisions.

A request processed earlier at the same time may reserve capacity before the
next equal-time request is considered.

## 5. Next state components

Later rolling-horizon checkpoints will add:

- accepted commitments;
- fixed future route plans;
- executed movements;
- remaining demand fragments;
- residual arc capacity;
- modifiable rerouting decisions.
