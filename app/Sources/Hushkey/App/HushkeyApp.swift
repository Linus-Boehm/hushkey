import AppKit
import SwiftUI

@main
struct HushkeyApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel()

    var body: some Scene {
        Window("Hushkey", id: "main") {
            HomeView(delegate: delegate).environment(model)
        }
        .windowResizability(.contentSize)
        .defaultPosition(.center)

        MenuBarExtra {
            MenuView().environment(model)
        } label: {
            MenuBarLabel(delegate: delegate).environment(model)
        }
        .menuBarExtraStyle(.window)

        Window("Welcome to Hushkey", id: "onboarding") {
            OnboardingView().environment(model)
        }
        .windowResizability(.contentSize)

        Window("Train on my mouth", id: "enroll") {
            EnrollmentView().environment(model)
        }
        .windowResizability(.contentSize)

        Window("Learn from dictation", id: "learning") {
            LearningView().environment(model)
        }
        .windowResizability(.contentSize)

        Settings {
            SettingsView().environment(model)
        }
    }
}

struct HomeView: View {
    let delegate: AppDelegate
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        MenuView()
            .padding(12)
            .task {
                delegate.model = model
                delegate.showMainWindow = {
                    openWindow(id: "main")
                    NSApp.activate(ignoringOtherApps: true)
                }
                model.start()
            }
    }
}

/// The menu-bar icon. Its `.task` runs at launch (menu-bar apps have no window), so it also
/// boots the model and opens onboarding when permissions are missing.
struct MenuBarLabel: View {
    let delegate: AppDelegate
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        icon.task {
            delegate.model = model
            model.start()
            let needs = !UserDefaults.standard.bool(forKey: AppSettings.Key.onboarded) || !model.cameraAuthorized || !model.accessibilityTrusted
            if needs {
                openWindow(id: "onboarding")
                NSApp.activate(ignoringOtherApps: true)
            }
        }
    }

    @ViewBuilder private var icon: some View {
        switch model.phase {
        case .listening: Image(systemName: "mouth.fill")
        case .transcribing: Image(systemName: "ellipsis.bubble")
        case .error: Image(systemName: "exclamationmark.bubble")
        case .idle: Image(systemName: "mouth")
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: AppModel?
    var showMainWindow: (() -> Void)?

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        MainActor.assumeIsolated { showMainWindow?() }
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { model?.shutdown() }
    }
}
