# Personal learning experiment

This fork adds an explicit correction-to-dataset loop and records AirPods motion
alongside Hushkey's camera input. It does **not** yet use motion in recognition,
automatically retrain, or promise general-purpose silent dictation accuracy.
The current pretrained decoder is English-oriented; German is not implemented.

## Use

1. Open **Learn from dictation…** from the menu bar and enable review.
2. Use the normal dictation hotkey to mouth a short English phrase. Camera access
   is required. Allow Motion if you want paired AirPods data; missing AirPods do
   not prevent camera-only examples.
3. Return to **Learn from dictation…**, correct the transcript to exactly what you
   mouthed, and choose **Confirm and save example**. The confirmation edits the
   training label only; it does not replace text already inserted into another app.
4. Repeat during ordinary use. Every new capture replaces the previous unsaved
   capture. Review is off after each app launch. Unconfirmed captures are never
   written to disk. Save is unavailable after ten minutes or a disconnect.
5. Choose **Start a new recording session** after re-seating AirPods or changing
   camera position. A fresh app launch also creates a new session ID.
6. Saved examples join the existing local enrollment set. **Train on my mouth…**
   exposes upstream's manual **Train personal adapter** action. It trains the
   camera model from accumulated examples; it does not consume motion metadata.

Aim for short phrases (under 20 seconds); upstream training excludes examples
longer than 600 resampled frames. There is no verified minimum number of examples
that makes personal silent dictation accurate.

## Local storage

`~/Library/Application Support/Hushkey/enrollment/` contains:

- `reviewed-<uuid>.npz`: mouth crops and derived visual features, plus confirmed text.
- `reviewed-<uuid>.json`: confirmed text, recording session ID, camera presentation
  timestamps, camera callback host uptimes, source-frame indices for the 25 fps
  model input, native AirPods timestamps, motion callback host uptimes,
  acceleration, rotation rate, attitude, and sensor status.
- `manifest.jsonl`: the existing trainer's input manifest, extended with session,
  metadata path and label-source fields. Existing readers accept these fields.

Only the latest reviewable utterance is held in server memory for each connection.
Saving requires its server-issued UUID. Repeated confirmation of that UUID on the
same connection returns the saved receipt without adding a second manifest row.
Discarding, starting another capture, or disconnecting makes an unsaved capture
unavailable. Enrollment through the separate prompt window retains upstream's
prompt-as-label behavior.

Camera and motion clocks are retained **without asserting precise synchronization**.
Host callback timestamps permit subsequent offset/drift investigation. AirPods
collection begins when dictation begins; camera pre-roll can precede motion.
Motion gaps/disconnections are visible in native sample timestamps and status;
there is no interpolation or fabricated motion data.

## Next experiments

1. Measure the pretrained camera decoder on a fixed set of unseen silent phrases.
2. Add stable session-level train/validation/test assignment. Upstream currently
   randomly splits all clips on each training run; do not treat that as evidence
   that an evolving personal model generalizes across sessions.
3. Train versioned candidate adapters on confirmed examples, compare against the
   installed model on the fixed validation set, and keep an independent test set
   for periodic reporting. Preserve rollback before enabling automatic promotion.
   Upstream's manual action currently writes `personal.pt`; back up a useful
   adapter before rerunning it.
4. Validate camera/CoreMotion clock alignment with a physical synchronized event.
5. Add a separate motion encoder and missing-input mask. Compare equally trained
   camera-only and camera-plus-motion models, plus shuffled-motion controls,
   on unseen recording sessions. Retain motion in decoding only if it helps.

More Subvox DTW word templates alone cannot create open-vocabulary recognition.
The camera model supplies the sentence decoder; AirPods' independent value is
an open research question. Never use an unconfirmed prediction as ground truth.

## Verification

Backend tests exercise actual synthetic-frame preprocessing, websocket capture,
confirmation, retry, discard, camera-only operation and trainer dataset loading.
The tiny test model validates plumbing only; its output is not usable dictation.
Real personal accuracy and physical sensor synchronization require recordings
from the person wearing the AirPods.
