// CoreMotion capture adapted from Subvox (MIT, © 2026 Joe Blau).
import CoreMotion
import Foundation
import Observation

/// Records only during an explicitly reviewable utterance. Motion is not used by the decoder yet.
@MainActor @Observable
final class AirPodsCapture {
    private(set) var status = "Not recording"
    private var points: [[String: Any]] = []
    private let manager = CMHeadphoneMotionManager()
    private var generation = UUID()

    func begin() {
        stop()
        points = []
        let current = UUID()
        generation = current
        guard manager.isDeviceMotionAvailable else {
            status = "Headphone motion unavailable"
            return
        }
        guard CMHeadphoneMotionManager.authorizationStatus() != .denied,
              CMHeadphoneMotionManager.authorizationStatus() != .restricted else {
            status = "Motion permission denied"
            return
        }
        status = "Waiting for AirPods"
        manager.startDeviceMotionUpdates(to: .main) { [weak self] motion, error in
            MainActor.assumeIsolated {
                guard let self, self.generation == current else { return }
                if let error { self.status = String(error.localizedDescription.prefix(180)); return }
                guard let motion else { return }
                self.status = "Recording AirPods motion"
                let a = motion.userAcceleration, r = motion.rotationRate, angle = motion.attitude
                self.points.append([
                    "t": motion.timestamp,
                    "callback_uptime": ProcessInfo.processInfo.systemUptime,
                    "acceleration": [a.x, a.y, a.z],
                    "rotation": [r.x, r.y, r.z],
                    "attitude": [angle.pitch, angle.roll, angle.yaw],
                ])
                // The server retains at most 30 seconds of camera data.
                self.points.removeAll { (motion.timestamp - ($0["t"] as? Double ?? 0)) > 30 }
                if self.points.count > 4000 { self.points.removeFirst(self.points.count - 4000) }
            }
        }
    }

    func finish(sessionID: UUID) -> [String: Any] {
        stop()
        let result: [String: Any] = ["session_id": sessionID.uuidString,
                                    "motion_status": status, "motion": points]
        points = []
        return result
    }

    func discard() {
        stop()
        points = []
        status = "Not recording"
    }

    func stop() {
        generation = UUID()
        manager.stopDeviceMotionUpdates()
    }
}
