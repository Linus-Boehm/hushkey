import SwiftUI

struct LearningView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        VStack(alignment: .leading, spacing: 14) {
            Text("Learn from dictation").font(.title2.bold())
            Toggle("Keep my next dictation available for review", isOn: Binding(
                get: { model.learningEnabled }, set: { model.setLearningEnabled($0) }))
                .disabled(model.isBusy || model.isSavingCapture)
            Text("While enabled, each dictation replaces the previous unsaved capture. Correct the words below and explicitly save them. Nothing is added to training automatically.")
                .foregroundStyle(.secondary)
            Text("AirPods: \(model.airPods.status)").font(.caption)
            Text("Motion is collected with the camera for future experiments; recognition currently uses the camera only.")
                .font(.caption).foregroundStyle(.secondary)
            Divider()
            Text("What you actually mouthed")
            TextEditor(text: $model.reviewText)
                .frame(height: 100)
                .border(.secondary.opacity(0.3))
                .disabled(model.pendingCaptureID == nil || model.isSavingCapture)
            HStack {
                Button(model.isSavingCapture ? "Saving…" : "Confirm and save example") { model.saveReviewedCapture() }
                    .disabled(model.pendingCaptureID == nil || model.isSavingCapture || model.isBusy || model.reviewText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                Button("Discard") { model.discardReviewedCapture() }
                    .disabled(model.pendingCaptureID == nil || model.isSavingCapture)
            }
            Text(model.reviewMessage).font(.callout).foregroundStyle(.secondary)
            Divider()
            Text("Saved examples join your local training set. Use “Train on my mouth…” to train a personal adapter manually. This does not yet train on AirPods data or automatically validate and deploy new models.")
                .font(.caption).foregroundStyle(.secondary)
            Button("Start a new recording session") { model.newLearningSession() }
                .disabled(model.isBusy || model.isSavingCapture)
            Text("Start a new session after re-seating AirPods or changing camera position. Unsaved captures expire after 10 minutes, the next recording, or a backend restart.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(24)
        .frame(width: 560)
    }
}
